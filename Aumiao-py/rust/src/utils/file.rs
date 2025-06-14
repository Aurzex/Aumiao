use once_cell::sync::Lazy;
use parking_lot::Mutex;
use serde_json::{Value, json};
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::Path;

// 使用 Lazy 和 Mutex 实现单例模式
static INSTANCE: Lazy<Mutex<CodeMaoFile>> = Lazy::new(|| Mutex::new(CodeMaoFile {}));

#[derive(Debug)]
pub enum FileError {
    IoError(io::Error),
    JsonError(serde_json::Error),
    UnsupportedType(String),
    InvalidBinaryMode(String),
    EncodingError(String),
    ValidationError(String),
    EmptyContent,
}

impl std::fmt::Display for FileError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FileError::IoError(e) => write!(f, "IO error: {}", e),
            FileError::JsonError(e) => write!(f, "JSON error: {}", e),
            FileError::UnsupportedType(t) => write!(f, "Unsupported type: {}", t),
            FileError::InvalidBinaryMode(m) => write!(f, "Invalid binary mode: {}", m),
            FileError::EncodingError(e) => write!(f, "Encoding error: {}", e),
            FileError::ValidationError(v) => write!(f, "Validation error: {}", v),
            FileError::EmptyContent => write!(f, "Empty content"),
        }
    }
}

impl std::error::Error for FileError {}

pub struct CodeMaoFile {}

impl CodeMaoFile {
    // 获取单例实例
    pub fn instance() -> &'static Mutex<Self> {
        &INSTANCE
    }

    // 检查文件是否存在且可以打开
    pub fn check_file(path: &Path) -> bool {
        match File::open(path) {
            Ok(_) => true,
            Err(err) => {
                eprintln!("{}", err);
                false
            }
        }
    }

    // 验证 JSON 字符串
    pub fn validate_json(json_string: &str) -> Result<Value, FileError> {
        serde_json::from_str(json_string).map_err(FileError::from)
    }

    // 从文件加载内容
    pub fn file_load(&self, path: &Path, file_type: &str) -> Result<Value, FileError> {
        if !Self::check_file(path) {
            return Ok(json!({}));
        }

        let mut file = File::open(path)?;
        let mut content = String::new();
        file.read_to_string(&mut content)?;

        match file_type {
            "json" => {
                if content.is_empty() {
                    Ok(json!({}))
                } else {
                    Ok(serde_json::from_str(&content)?)
                }
            }
            "txt" => Ok(Value::String(content)),
            _ => Err(FileError::UnsupportedType("不支持的读取方法".to_string())),
        }
    }

    // 写入文件
    pub fn file_write(
        path: &Path,
        content: &Value,
        method: &str,
        encoding: Option<&str>,
    ) -> Result<(), FileError> {
        // 确保父目录存在
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut mode = method.to_string();
        let is_binary = content.is_string()
            && content
                .as_str()
                .unwrap()
                .as_bytes()
                .iter()
                .any(|&b| b > 127);

        // 处理二进制模式
        if is_binary && !mode.contains('b') {
            mode.push('b');
        } else if !is_binary && mode.contains('b') {
            return Err(FileError::InvalidBinaryMode(format!(
                "文本内容不能使用二进制模式: {}",
                mode
            )));
        }

        let mut file = File::create(path)?;

        match content {
            Value::String(s) if is_binary => {
                file.write_all(s.as_bytes())?;
            }
            Value::String(s) => {
                if let Some(enc) = encoding {
                    // 这里可以根据需要添加编码处理
                    let _ = enc; // 暂时忽略编码参数
                }
                file.write_all(s.as_bytes())?;
            }
            Value::Array(arr) => {
                for line in arr {
                    if let Some(s) = line.as_str() {
                        writeln!(file, "{}", s)?;
                    }
                }
            }
            _ => {
                let json_str = serde_json::to_string_pretty(content)?;
                file.write_all(json_str.as_bytes())?;
            }
        }

        Ok(())
    }

    pub fn file_write_with_options(
        path: &Path,
        content: &Value,
        options: FileWriteOptions,
    ) -> Result<(), FileError> {
        // 确保父目录存在
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut file_options = fs::OpenOptions::new();
        file_options.write(true).create(true);

        if options.append {
            file_options.append(true);
        } else {
            file_options.truncate(true);
        }

        let mut file = file_options.open(path)?;

        match content {
            Value::String(s) if options.is_binary => {
                file.write_all(s.as_bytes())?;
            }
            Value::String(s) => {
                if let Some(enc) = options.encoding {
                    // 未来可以添加更多编码支持
                    match enc {
                        "utf-8" | "utf8" => file.write_all(s.as_bytes())?,
                        _ => {
                            return Err(FileError::EncodingError(format!(
                                "Unsupported encoding: {}",
                                enc
                            )));
                        }
                    }
                } else {
                    file.write_all(s.as_bytes())?;
                }
            }
            Value::Array(arr) => {
                for line in arr {
                    if let Some(s) = line.as_str() {
                        writeln!(file, "{}", s)?;
                    }
                }
            }
            _ => {
                let json_str = serde_json::to_string_pretty(content)?;
                file.write_all(json_str.as_bytes())?;
            }
        }

        file.flush()?;
        Ok(())
    }

    pub fn validate_content(&self, content: &[u8]) -> Result<Value, FileError> {
        if content.is_empty() {
            return Err(FileError::EmptyContent);
        }

        match String::from_utf8(content.to_vec()) {
            Ok(s) => self.validate_json(&s),
            Err(e) => Err(FileError::EncodingError(e.to_string())),
        }
    }
}

#[derive(Debug)]
pub struct FileWriteOptions<'a> {
    pub append: bool,
    pub is_binary: bool,
    pub encoding: Option<&'a str>,
}

impl<'a> Default for FileWriteOptions<'a> {
    fn default() -> Self {
        Self {
            append: false,
            is_binary: false,
            encoding: Some("utf-8"),
        }
    }
}

// 便捷函数，用于获取单例实例
pub fn get_instance() -> &'static Mutex<CodeMaoFile> {
    CodeMaoFile::instance()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use tempfile::tempdir;

    #[test]
    fn test_file_operations() {
        let temp_dir = tempdir().unwrap();
        let file_path = temp_dir.path().join("test.json");

        // 测试写入 JSON
        let content = json!({
            "name": "test",
            "value": 42
        });

        CodeMaoFile::file_write(&file_path, &content, "w", None).unwrap();

        // 测试读取 JSON
        let instance = CodeMaoFile::instance();
        let guard = instance.lock();
        let loaded = guard.file_load(&file_path, "json").unwrap();

        assert_eq!(loaded["name"], "test");
        assert_eq!(loaded["value"], 42);
    }

    #[test]
    fn test_file_write_with_options() {
        let temp_dir = tempdir().unwrap();
        let file_path = temp_dir.path().join("test_append.txt");

        // Test append mode
        let content1 = json!("First line\n");
        let content2 = json!("Second line");

        let options = FileWriteOptions {
            append: false,
            ..Default::default()
        };
        CodeMaoFile::file_write_with_options(&file_path, &content1, options).unwrap();

        let options = FileWriteOptions {
            append: true,
            ..Default::default()
        };
        CodeMaoFile::file_write_with_options(&file_path, &content2, options).unwrap();

        // Verify content
        let instance = CodeMaoFile::instance();
        let guard = instance.lock();
        let loaded = guard.file_load(&file_path, "txt").unwrap();

        let content = loaded.as_str().unwrap();
        assert!(content.contains("First line"));
        assert!(content.contains("Second line"));
    }

    #[test]
    fn test_validate_content() {
        let instance = CodeMaoFile::instance();
        let guard = instance.lock();

        // Test valid JSON
        let valid_json = b"{\"test\": \"value\"}";
        assert!(guard.validate_content(valid_json).is_ok());

        // Test invalid JSON
        let invalid_json = b"{test: value}";
        assert!(guard.validate_content(invalid_json).is_err());

        // Test empty content
        let empty = b"";
        assert!(matches!(
            guard.validate_content(empty),
            Err(FileError::EmptyContent)
        ));

        // Test invalid UTF-8
        let invalid_utf8 = &[0xFF, 0xFF, 0xFF];
        assert!(matches!(
            guard.validate_content(invalid_utf8),
            Err(FileError::EncodingError(_))
        ));
    }
}
