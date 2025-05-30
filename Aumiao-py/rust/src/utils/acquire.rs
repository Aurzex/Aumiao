use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;
use tokio::time::sleep;

use async_trait::async_trait;
use futures::stream::{Stream, StreamExt};
use lazy_static::lazy_static;
use log::{debug, error, info};
use once_cell::sync::Lazy;
use parking_lot::Mutex;
use reqwest::{Client, ClientBuilder, Cookie, Method, Response, StatusCode};
use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::fs::File;
use url::Url;

use crate::singleton;
use crate::utils::data::SettingManager;
use crate::utils::{data, file, tool};

// Constants
const BASE_URL: &str = "https://api.codemao.cn";
const MAX_RETRIES: u32 = 3;
const BACKOFF_FACTOR: f64 = 0.3;
const TIMEOUT_SECONDS: u64 = 10;
const MAX_CHARACTER: usize = 100;

lazy_static! {
    static ref LOG_DIR: PathBuf = data::CURRENT_DIR.join(".log");
    static ref LOG_FILE_PATH: PathBuf =
        LOG_DIR.join(format!("{}.txt", tool::TimeUtils::current_timestamp(10)));
}

#[derive(Debug, Error)]
pub enum AcquireError {
    #[error("HTTP错误: {0}")]
    Http(#[from] reqwest::Error),
    #[error("IO错误: {0}")]
    Io(#[from] std::io::Error),
    #[error("URL解析错误: {0}")]
    Url(#[from] url::ParseError),
    #[error("JSON解析错误: {0}")]
    Json(#[from] serde_json::Error),
    #[error("无效的Cookie格式")]
    InvalidCookie,
    #[error("请求失败: {0}")]
    RequestFailed(String),
    #[error("未知错误: {0}")]
    Unknown(String),
}

pub type Result<T> = std::result::Result<T, AcquireError>;

#[derive(Debug, Clone, Default)]
pub struct Token {
    pub average: String,
    pub edu: String,
    pub judgement: String,
    pub blank: String,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum HttpStatus {
    Created = 201,
    Forbidden = 403,
    NotFound = 404,
    NotModified = 304,
    NoContent = 204,
    Ok = 200,
}

#[derive(Debug, Clone)]
pub struct CodeMaoClient {
    client: Client,
    base_url: String,
    headers: Arc<Mutex<reqwest::header::HeaderMap>>,
    token: Token,
    settings: Arc<data::CodeMaoSetting>,
}

singleton!(CodeMaoClient);

impl CodeMaoClient {
    pub fn new() -> Result<Self> {
        std::fs::create_dir_all(&*LOG_DIR)?;

        let client = ClientBuilder::new()
            .timeout(Duration::from_secs(TIMEOUT_SECONDS))
            .cookie_store(true)
            .build()?;

        let settings = Arc::new(data::SettingManager::instance().get_data());
        let mut headers = reqwest::header::HeaderMap::new();

        for (key, value) in &settings.PROGRAM.HEADERS {
            headers.insert(
                reqwest::header::HeaderName::from_bytes(key.as_bytes())?,
                reqwest::header::HeaderValue::from_str(value)?,
            );
        }

        Ok(Self {
            client,
            base_url: BASE_URL.to_string(),
            headers: Arc::new(Mutex::new(headers)),
            token: Token::default(),
            settings,
        })
    }

    pub async fn send_request(
        &self,
        endpoint: &str,
        method: Method,
        params: Option<serde_json::Value>,
        payload: Option<serde_json::Value>,
        files: Option<Vec<(String, Vec<u8>)>>,
        headers: Option<reqwest::header::HeaderMap>,
        retries: Option<u32>,
        timeout: Option<Duration>,
    ) -> Result<Response> {
        let url = if endpoint.starts_with("http") {
            endpoint.to_string()
        } else {
            format!("{}{}", self.base_url, endpoint)
        };

        let mut request_builder = self.client.request(method.clone(), &url);

        // 添加请求头
        let mut merged_headers = self.headers.lock().clone();
        if let Some(h) = headers {
            merged_headers.extend(h);
        }
        request_builder = request_builder.headers(merged_headers);

        // 添加查询参数
        if let Some(p) = params {
            request_builder = request_builder.query(&p);
        }

        // 添加请求体
        if let Some(p) = payload {
            request_builder = request_builder.json(&p);
        }

        // 添加文件
        if let Some(files) = files {
            let form = reqwest::multipart::Form::new();
            for (name, data) in files {
                let part = reqwest::multipart::Part::bytes(data)
                    .file_name(name.clone())
                    .mime_str("application/octet-stream")?;
                request_builder = request_builder.multipart(form.part(name, part));
            }
        }

        // 设置超时
        if let Some(t) = timeout {
            request_builder = request_builder.timeout(t);
        }

        let retries = retries.unwrap_or(MAX_RETRIES);
        let mut last_error = None;

        for attempt in 0..retries {
            match request_builder.try_clone().unwrap().send().await {
                Ok(response) => {
                    debug!("Request {} {} {}", method, url, response.status());
                    if response.status().is_success() {
                        return Ok(response);
                    }
                    last_error = Some(AcquireError::RequestFailed(format!(
                        "HTTP {} - {}",
                        response.status(),
                        response.text().await?
                    )));
                }
                Err(e) => {
                    error!("Request failed (attempt {}): {}", attempt + 1, e);
                    last_error = Some(AcquireError::Http(e));
                    sleep(Duration::from_secs_f64(
                        BACKOFF_FACTOR * (2_f64.powi(attempt as i32)),
                    ))
                    .await;
                }
            }
        }

        Err(last_error.unwrap_or_else(|| AcquireError::Unknown("Maximum retries exceeded".into())))
    }

    pub fn update_cookies(&self, cookies: &str) -> Result<()> {
        let mut headers = self.headers.lock();
        headers.remove("Cookie");
        headers.insert(
            "Cookie",
            cookies.parse().map_err(|_| AcquireError::InvalidCookie)?,
        );
        Ok(())
    }

    pub async fn fetch_data<T>(
        &self,
        endpoint: &str,
        params: serde_json::Value,
        payload: Option<serde_json::Value>,
        limit: Option<usize>,
        method: Method,
        total_key: &str,
        data_key: &str,
        pagination_method: &str,
        config: Option<PaginationConfig>,
    ) -> Result<impl Stream<Item = Result<T>>>
    where
        T: for<'de> Deserialize<'de> + Send + 'static,
    {
        let initial_response = self
            .send_request(
                endpoint,
                method.clone(),
                Some(params.clone()),
                payload.clone(),
                None,
                None,
                None,
                None,
            )
            .await?;

        let initial_data: serde_json::Value = initial_response.json().await?;
        let data_processor = tool::DataProcessor::new();

        let total_items = data_processor
            .get_nested_value(&initial_data, total_key)
            .and_then(|v| v.as_u64())
            .ok_or_else(|| AcquireError::Unknown("Failed to get total items".into()))?
            as usize;

        let config = config.unwrap_or_else(|| PaginationConfig {
            amount_key: "limit".to_string(),
            offset_key: if method == Method::GET {
                "offset"
            } else {
                "current_page"
            }
            .to_string(),
            response_amount_key: "limit".to_string(),
            response_offset_key: "offset".to_string(),
        });

        let items_per_page = params
            .get(&config.amount_key)
            .and_then(|v| v.as_u64())
            .unwrap_or(
                initial_data
                    .get(&config.response_amount_key)
                    .and_then(|v| v.as_u64())
                    .unwrap_or(5),
            ) as usize;

        if items_per_page <= 0 {
            return Err(AcquireError::Unknown("Invalid items per page".into()));
        }

        let total_pages = (total_items + items_per_page - 1) / items_per_page;

        let stream = futures::stream::iter(0..total_pages)
            .map(move |page| {
                let mut page_params = params.clone();
                match pagination_method {
                    "offset" => {
                        page_params[&config.offset_key] = json!(page * items_per_page);
                    }
                    "page" => {
                        page_params[&config.offset_key] = json!(page + 1);
                    }
                    _ => {
                        return futures::stream::once(async {
                            Err(AcquireError::Unknown(
                                "Unsupported pagination method".into(),
                            ))
                        })
                        .boxed();
                    }
                }

                let future = async move {
                    let response = self
                        .send_request(
                            endpoint,
                            method.clone(),
                            Some(page_params),
                            payload.clone(),
                            None,
                            None,
                            None,
                            None,
                        )
                        .await?;

                    let page_data: serde_json::Value = response.json().await?;
                    let items = match page_data.get(data_key) {
                        Some(array) => array,
                        None => return Err(AcquireError::Unknown("Data key not found".into())),
                    };

                    let mut yielded_count = 0;
                    let stream = futures::stream::iter(items.as_array().unwrap_or(&vec![]).iter())
                        .map(|item| {
                            serde_json::from_value(item.clone()).map_err(AcquireError::Json)
                        })
                        .take_while(move |_| {
                            yielded_count += 1;
                            future::ready(limit.map_or(true, |l| yielded_count <= l))
                        });

                    Ok(stream)
                };

                Box::pin(future) as futures::future::BoxFuture<_>
            })
            .buffer_unordered(3)
            .flat_map(|result| match result {
                Ok(stream) => stream,
                Err(e) => futures::stream::once(async move { Err(e) }).boxed(),
            });

        let stream = if let Some(limit) = limit {
            Box::pin(stream.take(limit))
        } else {
            Box::pin(stream)
        };

        Ok(stream)
    }

    pub async fn switch_account(&mut self, token: &str, identity: &str) -> Result<()> {
        // 更新 Token
        match identity {
            "average" => self.token.average = token.to_string(),
            "edu" => self.token.edu = token.to_string(),
            "judgement" => self.token.judgement = token.to_string(),
            "blank" => self.token.blank = token.to_string(),
            _ => return Err(AcquireError::Unknown("Invalid identity".into())),
        }

        // 更新 Authorization header
        let mut headers = self.headers.lock();
        headers.insert(
            reqwest::header::AUTHORIZATION,
            format!("Bearer {}", token)
                .parse()
                .map_err(|_| AcquireError::InvalidCookie)?,
        );

        info!("Switched to {} account", identity);
        Ok(())
    }

    async fn log_request(&self, response: &Response) -> Result<()> {
        if !self.settings.PARAMETER.log {
            return Ok(());
        }

        let mut log_content = format!(
            "[{}]\n",
            tool::TimeUtils::format_timestamp(Some(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)?
                    .as_secs() as i64
            ))
        );

        log_content.push_str(&format!(
            "Method: {}\nURL: {}\nStatus: {}\n{}\n",
            response.method(),
            response.url(),
            response.status(),
            "*".repeat(50)
        ));

        // 记录请求头
        log_content.push_str("Request Headers:\n");
        for (key, value) in response.headers() {
            log_content.push_str(&format!("{}: {}\n", key, value.to_str()?));
        }
        log_content.push_str(&"*".repeat(50));
        log_content.push('\n');

        // 记录响应内容
        log_content.push_str("Response:\n");
        let response_text = response.text().await?;
        if response_text.len() <= MAX_CHARACTER {
            log_content.push_str(&response_text);
        } else {
            log_content.push_str(&format!("{}...", &response_text[..MAX_CHARACTER]));
        }
        log_content.push_str(&format!("\n{}\n\n", "=".repeat(50)));

        // 写入日志文件
        tokio::fs::create_dir_all(&*LOG_DIR).await?;
        let mut file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&*LOG_FILE_PATH)
            .await?;

        use tokio::io::AsyncWriteExt;
        file.write_all(log_content.as_bytes()).await?;
        file.flush().await?;

        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct PaginationConfig {
    pub amount_key: String,
    pub offset_key: String,
    pub response_amount_key: String,
    pub response_offset_key: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tokio::test;

    #[test]
    async fn test_client_creation() {
        let client = CodeMaoClient::new().unwrap();
        assert!(!client.base_url.is_empty());
    }

    #[test]
    async fn test_send_request() {
        let client = CodeMaoClient::new().unwrap();
        let response = client
            .send_request(
                "/test",
                Method::GET,
                None,
                None,
                None,
                None,
                Some(1),
                Some(Duration::from_secs(1)),
            )
            .await;

        // 这里会失败，因为是测试URL
        assert!(response.is_err());
    }

    #[test]
    async fn test_account_switching() {
        let mut client = CodeMaoClient::new().unwrap();
        let result = client.switch_account("test_token", "average").await;
        assert!(result.is_ok());
        assert_eq!(client.token.average, "test_token");
    }
}
