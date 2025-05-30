use lazy_static::lazy_static;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use crate::singleton;

// 常量定义
lazy_static! {
    pub static ref CURRENT_DIR: PathBuf = std::env::current_dir().unwrap();
    pub static ref DATA_DIR: PathBuf = CURRENT_DIR.join("data");
    pub static ref CACHE_FILE_PATH: PathBuf = DATA_DIR.join("cache.json");
    pub static ref DATA_FILE_PATH: PathBuf = DATA_DIR.join("data.json");
    pub static ref SETTING_FILE_PATH: PathBuf = DATA_DIR.join("setting.json");
}

// 确保数据目录存在
pub fn init_data_dir() {
    fs::create_dir_all(&*DATA_DIR).unwrap();
}

// 数据结构定义
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AccountData {
    #[serde(default)]
    pub author_level: String,
    #[serde(default)]
    pub create_time: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub identity: String,
    #[serde(default)]
    pub nickname: String,
    #[serde(default)]
    pub password: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UserData {
    #[serde(default)]
    pub ads: Vec<String>,
    #[serde(default)]
    pub answers: Vec<HashMap<String, serde_json::Value>>,
    #[serde(default)]
    pub black_room: Vec<String>,
    #[serde(default)]
    pub comments: Vec<String>,
    #[serde(default)]
    pub emojis: Vec<String>,
    #[serde(default)]
    pub replies: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CodeMaoData {
    #[serde(default)]
    pub ACCOUNT_DATA: AccountData,
    #[serde(default)]
    pub INFO: HashMap<String, String>,
    #[serde(default)]
    pub USER_DATA: UserData,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Parameter {
    #[serde(default)]
    pub all_read_type: Vec<String>,
    #[serde(default)]
    pub cookie_check_url: String,
    #[serde(default)]
    pub log: bool,
    #[serde(default)]
    pub password_login_method: String,
    #[serde(default)]
    pub report_work_max: i32,
    #[serde(default)]
    pub spam_del_max: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ExtraBody {
    #[serde(default)]
    pub enable_search: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct More {
    #[serde(default)]
    pub extra_body: ExtraBody,
    #[serde(default)]
    pub stream: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DashscopePlugin {
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub more: More,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Plugin {
    #[serde(default)]
    pub DASHSCOPE: DashscopePlugin,
    #[serde(default)]
    pub prompt: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Program {
    #[serde(default)]
    pub AUTHOR: String,
    #[serde(default)]
    pub HEADERS: HashMap<String, String>,
    #[serde(default)]
    pub MEMBER: String,
    #[serde(default)]
    pub SLOGAN: String,
    #[serde(default)]
    pub TEAM: String,
    #[serde(default)]
    pub VERSION: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CodeMaoCache {
    #[serde(default)]
    pub collected: i32,
    #[serde(default)]
    pub fans: i32,
    #[serde(default)]
    pub level: i32,
    #[serde(default)]
    pub liked: i32,
    #[serde(default)]
    pub nickname: String,
    #[serde(default)]
    pub timestamp: i64,
    #[serde(default)]
    pub user_id: i32,
    #[serde(default)]
    pub view: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CodeMaoSetting {
    #[serde(default)]
    pub PARAMETER: Parameter,
    #[serde(default)]
    pub PLUGIN: Plugin,
    #[serde(default)]
    pub PROGRAM: Program,
}

// 错误类型定义
#[derive(Debug)]
pub enum DataError {
    IoError(std::io::Error),
    SerdeError(serde_json::Error),
    Custom(String),
}

impl From<std::io::Error> for DataError {
    fn from(err: std::io::Error) -> Self {
        DataError::IoError(err)
    }
}

impl From<serde_json::Error> for DataError {
    fn from(err: serde_json::Error) -> Self {
        DataError::SerdeError(err)
    }
}

// 通用数据管理器 trait
pub trait DataManager: Sized {
    type Data: Serialize + for<'de> Deserialize<'de> + Default;

    fn get_file_path() -> &'static Path;

    fn load() -> Result<Self::Data, DataError> {
        let path = Self::get_file_path();
        if !path.exists() {
            return Ok(Self::Data::default());
        }
        let content = fs::read_to_string(path)?;
        let data = serde_json::from_str(&content)?;
        Ok(data)
    }

    fn save(&self, data: &Self::Data) -> Result<(), DataError> {
        let path = Self::get_file_path();
        let content = serde_json::to_string_pretty(data)?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(path, content)?;
        Ok(())
    }
}

// 具体管理器实现
pub struct DataManagerImpl<T> {
    data: Mutex<T>,
}

impl<T: Serialize + for<'de> Deserialize<'de> + Default> DataManagerImpl<T> {
    fn new() -> Self {
        Self {
            data: Mutex::new(T::default()),
        }
    }

    pub fn get_data(&self) -> T
    where
        T: Clone,
    {
        self.data.lock().unwrap().clone()
    }

    pub fn update(&self, new_data: T) {
        *self.data.lock().unwrap() = new_data;
    }
}

// 单例管理器实现
macro_rules! impl_singleton_manager {
    ($name:ident, $data_type:ty, $file_path:expr) => {
        pub struct $name {
            inner: DataManagerImpl<$data_type>,
        }

        impl $name {
            fn new() -> Self {
                Self {
                    inner: DataManagerImpl::new(),
                }
            }
        }

        singleton!($name);
    };
}

// 定义具体的单例管理器
impl_singleton_manager!(CodeMaoDataManager, CodeMaoData, DATA_FILE_PATH);
impl_singleton_manager!(CodeMaoCacheManager, CodeMaoCache, CACHE_FILE_PATH);
impl_singleton_manager!(CodeMaoSettingManager, CodeMaoSetting, SETTING_FILE_PATH);
