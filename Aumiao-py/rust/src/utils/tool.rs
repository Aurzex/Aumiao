use chrono::{Local, TimeZone};
use html_escape;
use rand::prelude::*;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::iter::Iterator;

// 自定义类型定义
pub type JsonDict = HashMap<String, Value>;
pub type DataObject = Value;

#[derive(Debug)]
pub enum DataError {
    ValueError(String),
    TypeError(String),
    Other(String),
}

impl std::fmt::Display for DataError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DataError::ValueError(msg) => write!(f, "ValueError: {}", msg),
            DataError::TypeError(msg) => write!(f, "TypeError: {}", msg),
            DataError::Other(msg) => write!(f, "Error: {}", msg),
        }
    }
}

type Result<T> = std::result::Result<T, DataError>;

pub struct DataProcessor;

impl DataProcessor {
    pub fn filter_by_nested_values(
        data: &Value,
        id_path: &str,
        target_values: &[Value],
        strict_mode: bool,
    ) -> Result<Vec<Value>> {
        if id_path.is_empty() {
            return Err(DataError::ValueError("id_path 必须是非空字符串".into()));
        }

        let data_vec = Self::normalize_input(data)?;
        let path_keys: Vec<&str> = id_path.split('.').collect();

        let mut results = Vec::new();
        for item in data_vec {
            let mut current_value = &item;

            for key in &path_keys {
                if !current_value.is_object() {
                    if strict_mode {
                        return Err(DataError::ValueError(format!(
                            "路径 {} 处遇到非字典类型",
                            key
                        )));
                    }
                    current_value = &Value::Null;
                    break;
                }

                if let Some(next_value) = current_value.get(key) {
                    current_value = next_value;
                } else {
                    current_value = &Value::Null;
                    break;
                }
            }

            if target_values.contains(current_value) {
                results.push(item.clone());
            }
        }

        Ok(results)
    }

    fn is_item_container(data: &Value) -> bool {
        if let Value::Object(map) = data {
            if let Some(items) = map.get("items") {
                return items.is_array();
            }
        }
        false
    }

    fn normalize_input(data: &Value) -> Result<Vec<Value>> {
        match data {
            Value::Object(map) if Self::is_item_container(data) => {
                if let Some(Value::Array(items)) = map.get("items") {
                    Ok(items.clone())
                } else {
                    Ok(vec![])
                }
            }
            Value::Object(_) => Ok(vec![data.clone()]),
            Value::Array(arr) => Ok(arr.clone()),
            _ => Err(DataError::TypeError(
                "输入数据必须是字典或可迭代的字典集合".into(),
            )),
        }
    }

    pub fn filter_data(
        data: &Value,
        include: Option<&[String]>,
        exclude: Option<&[String]>,
    ) -> Result<Value> {
        if include.is_some() && exclude.is_some() {
            return Err(DataError::ValueError("不能同时指定包含和排除字段".into()));
        }

        fn filter_object(
            obj: &serde_json::Map<String, Value>,
            include: Option<&[String]>,
            exclude: Option<&[String]>,
        ) -> serde_json::Map<String, Value> {
            let mut result = serde_json::Map::new();
            for (k, v) in obj {
                let should_include = match (include, exclude) {
                    (Some(incl), None) => incl.contains(k),
                    (None, Some(excl)) => !excl.contains(k),
                    (None, None) => true,
                    _ => false,
                };
                if should_include {
                    result.insert(k.clone(), v.clone());
                }
            }
            result
        }

        match data {
            Value::Object(obj) => Ok(Value::Object(filter_object(obj, include, exclude))),
            Value::Array(arr) => {
                let filtered: Vec<Value> = arr
                    .iter()
                    .filter_map(|item| {
                        if let Value::Object(obj) = item {
                            Some(Value::Object(filter_object(obj, include, exclude)))
                        } else {
                            None
                        }
                    })
                    .collect();
                Ok(Value::Array(filtered))
            }
            _ => Err(DataError::TypeError(format!(
                "不支持的数据类型: {:?}",
                data
            ))),
        }
    }

    pub fn get_nested_value(data: &Value, path: &str) -> Option<&Value> {
        let mut current = data;
        for key in path.split('.') {
            match current.as_object() {
                Some(obj) => {
                    if let Some(value) = obj.get(key) {
                        current = value;
                    } else {
                        return None;
                    }
                }
                None => return None,
            }
        }
        Some(current)
    }

    fn normalize_input(data: &Value) -> Result<Vec<Value>, DataError> {
        match data {
            Value::Object(obj) if Self::_is_item_container(data) => {
                if let Some(Value::Array(items)) = obj.get("items") {
                    Ok(items.clone())
                } else {
                    Ok(vec![])
                }
            }
            Value::Object(_) => Ok(vec![data.clone()]),
            Value::Array(arr) => Ok(arr.clone()),
            _ => Err(DataError::TypeError(
                "输入数据必须是字典或可迭代的字典集合".into(),
            )),
        }
    }

    fn _is_item_container(data: &Value) -> bool {
        if let Value::Object(obj) = data {
            if let Some(items) = obj.get("items") {
                return items.is_array();
            }
        }
        false
    }

    pub fn deduplicate<T: Eq + std::hash::Hash + Clone>(sequence: &[T]) -> Vec<T> {
        let mut seen = HashSet::new();
        let mut result = Vec::new();
        for item in sequence {
            if seen.insert(item.clone()) {
                result.push(item.clone());
            }
        }
        result
    }
}

pub struct DataConverter;

impl DataConverter {
    pub fn convert_cookie(cookie: &HashMap<String, String>) -> String {
        cookie
            .iter()
            .map(|(k, v)| format!("{}={}", k, v))
            .collect::<Vec<_>>()
            .join("; ")
    }

    pub fn html_to_text(html_content: &str, config: Option<HtmlToTextConfig>) -> String {
        let config = config.unwrap_or_default();
        let paragraph_regex = Regex::new(r"<p\b[^>]*>(.*?)</p>").unwrap();

        // 提取外层段落
        let outer_match = Regex::new(r"<p\b[^>]*>(.*)</p>").unwrap();
        let inner_content = if let Some(captures) = outer_match.captures(html_content) {
            captures.get(1).map_or(html_content, |m| m.as_str()).trim()
        } else {
            html_content
        };

        // 提取所有段落
        let mut paragraphs: Vec<&str> = paragraph_regex
            .find_iter(inner_content)
            .map(|m| m.as_str())
            .collect();

        // 处理无段落情况
        if paragraphs.is_empty() {
            paragraphs.push(inner_content);
        }

        let mut processed = Vec::new();
        for content in paragraphs {
            let mut text = content.to_string();

            // 处理图片标签
            if config.replace_images {
                let img_regex =
                    Regex::new(r#"<img\b[^>]*?src\s*=\s*("([^"]+)"|'([^']+)'|([^\s>]+))[^>]*>"#)
                        .unwrap();
                text = img_regex
                    .replace_all(&text, |caps: &regex::Captures| {
                        let src = caps
                            .iter()
                            .skip(2)
                            .find_map(|m| m.map(|m| m.as_str()))
                            .unwrap_or("");
                        let unescaped_src = html_escape::decode_html_entities(src);
                        config.img_format.replace("{src}", &unescaped_src)
                    })
                    .to_string();
            }

            // 移除HTML标签
            let tag_regex = Regex::new(r"<[^>]+>").unwrap();
            text = tag_regex.replace_all(&text, "").to_string();

            // HTML实体解码
            if config.unescape_entities {
                text = html_escape::decode_html_entities(&text).into_owned();
            }

            // 处理换行
            text = text.trim().to_string();
            if !config.keep_line_breaks {
                text = text.replace('\n', " ");
            }

            processed.push(text);
        }

        // 构建结果
        let mut result = processed.join("\n");

        // 合并空行
        if config.merge_empty_lines {
            let empty_lines_pattern = Regex::new(r"\n{2,}").unwrap();
            result = empty_lines_pattern.replace_all(&result, "\n").to_string();
        }

        result.trim().to_string()
    }

    pub fn to_serializable<T: serde::Serialize>(data: &T) -> Result<Value, DataError> {
        serde_json::to_value(data).map_err(|e| DataError::TypeError(e.to_string()))
    }
}

pub struct StringProcessor;

impl StringProcessor {
    pub fn insert_zero_width(text: &str) -> String {
        text.chars()
            .map(|c| format!("\u{200b}{}", c))
            .collect::<String>()
            .trim_start_matches('\u{200b}')
            .to_string()
    }

    pub fn find_substrings(text: &str, candidates: &[String]) -> (Option<i32>, Option<i32>) {
        for candidate in candidates {
            if candidate.contains(text) {
                if let Some((part1, part2)) = candidate.split_once('.') {
                    if let (Ok(n1), Ok(n2)) = (part1.parse::<i32>(), part2.parse::<i32>()) {
                        return (Some(n1), Some(n2));
                    }
                }
            }
        }
        (None, None)
    }
}

pub struct TimeUtils;

impl TimeUtils {
    pub fn current_timestamp(length: u32) -> i64 {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap();

        match length {
            10 => now.as_secs() as i64,
            13 => now.as_millis() as i64,
            _ => panic!(
                "Invalid timestamp length: {}. Valid options are 10 or 13",
                length
            ),
        }
    }

    pub fn format_timestamp(ts: Option<i64>) -> String {
        use chrono::{Local, TimeZone};

        let dt = match ts {
            Some(ts) => {
                if ts > 1_000_000_000_000 {
                    // 假设是毫秒
                    Local.timestamp_millis_opt(ts).unwrap()
                } else {
                    Local.timestamp_opt(ts, 0).unwrap()
                }
            }
            None => Local::now(),
        };
        dt.format("%Y-%m-%d %H:%M:%S").to_string()
    }
}

pub struct DataAnalyzer;

impl DataAnalyzer {
    pub fn compare_datasets(
        &self,
        before: &Value,
        after: &Value,
        metrics: &HashMap<String, String>,
        timestamp_field: Option<&str>,
    ) -> Result<()> {
        let before_dict = self._to_dict(before)?;
        let after_dict = self._to_dict(after)?;

        if let Some(field) = timestamp_field {
            if let (Some(before_ts), Some(after_ts)) = (
                before_dict.get(field).and_then(Value::as_i64),
                after_dict.get(field).and_then(Value::as_i64),
            ) {
                println!(
                    "时间段: {} → {}",
                    TimeUtils::format_timestamp(Some(before_ts)),
                    TimeUtils::format_timestamp(Some(after_ts))
                );
            }
        }

        for (field, label) in metrics {
            let before_val = before_dict.get(field).and_then(Value::as_i64).unwrap_or(0);
            let after_val = after_dict.get(field).and_then(Value::as_i64).unwrap_or(0);
            println!(
                "{}: {:+} (当前: {}, 初始: {})",
                label,
                after_val - before_val,
                after_val,
                before_val
            );
        }

        Ok(())
    }

    fn _to_dict(&self, data: &Value) -> Result<&serde_json::Map<String, Value>> {
        match data {
            Value::Object(map) => Ok(map),
            _ => Err(DataError::ValueError("数据格式转换失败".into())),
        }
    }
}

pub struct DataMerger;

impl DataMerger {
    pub fn merge(datasets: &[Value]) -> Result<Value> {
        let mut merged = serde_json::Map::new();

        for data in datasets.iter().filter(|d| !d.is_null()) {
            if let Value::Object(map) = data {
                for (key, value) in map {
                    match value {
                        Value::Object(obj) => {
                            if let Some(Value::Object(existing)) = merged.get_mut(key) {
                                existing.extend(obj.clone());
                            } else {
                                merged.insert(key.clone(), Value::Object(obj.clone()));
                            }
                        }
                        _ => {
                            merged.insert(key.clone(), value.clone());
                        }
                    }
                }
            }
        }

        Ok(Value::Object(merged))
    }
}

pub struct MathUtils;

impl MathUtils {
    pub fn clamp(value: i32, min_val: i32, max_val: i32) -> i32 {
        value.max(min_val).min(max_val)
    }
}

pub struct StudentDataGenerator;

impl StudentDataGenerator {
    const CLASS_NUM_LIMIT: i32 = 12;
    const LETTER_PROBABILITY: f64 = 0.3;
    const SPECIALTY_PROBABILITY: f64 = 0.4;
    const NAME_SUFFIX_PROBABILITY: f64 = 0.2;

    fn number_to_chinese(n: i32) -> String {
        let chinese_numbers = [
            "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二",
        ];
        if (1..=Self::CLASS_NUM_LIMIT).contains(&n) {
            chinese_numbers[(n - 1) as usize].to_string()
        } else {
            n.to_string()
        }
    }

    pub fn generate_class_names(
        num_classes: usize,
        grade_range: (i32, i32),
        use_letters: bool,
        add_specialty: bool,
    ) -> Vec<String> {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        let specialties = vec![
            "实验", "重点", "国际", "理科", "文科", "艺术", "体育", "国防",
        ];
        let letters = vec!["A", "B", "C", "D"];

        let mut class_names = Vec::with_capacity(num_classes);
        for _ in 0..num_classes {
            let grade = rng.gen_range(grade_range.0..=grade_range.1);
            let grade_str = format!("{}年级", Self::number_to_chinese(grade));

            let class_num = if use_letters && rng.gen_bool(Self::LETTER_PROBABILITY) {
                letters.choose(&mut rng).unwrap().to_string()
            } else {
                rng.gen_range(1..=20).to_string()
            };

            let specialty = if add_specialty && rng.gen_bool(Self::SPECIALTY_PROBABILITY) {
                specialties.choose(&mut rng).unwrap().to_string()
            } else {
                String::new()
            };

            let class_name = format!("{}{}{}{}", grade_str, class_num, specialty, "班");
            class_names.push(class_name);
        }

        class_names
    }

    pub fn generate_student_names(num_students: usize, gender: Option<&str>) -> Vec<String> {
        use rand::Rng;
        let mut rng = rand::thread_rng();

        let surnames = vec![
            "李", "王", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴", "徐", "孙", "马", "朱",
            "胡", "郭", "何", "高", "林", "罗",
        ];

        let male_names = vec![
            "浩", "宇", "轩", "杰", "博", "晨", "俊", "鑫", "昊", "睿", "涛", "鹏", "翔", "泽",
            "楷", "子轩", "浩然", "俊杰", "宇航",
        ];

        let female_names = vec![
            "欣", "怡", "婷", "雨", "梓", "涵", "诗", "静", "雅", "娜", "雪", "雯", "璐", "颖",
            "琳", "雨萱", "梓涵", "诗琪", "欣怡",
        ];

        let mut names = Vec::with_capacity(num_students);
        for _ in 0..num_students {
            let surname = surnames.choose(&mut rng).unwrap();

            let current_gender =
                gender.unwrap_or_else(|| if rng.gen_bool(0.5) { "male" } else { "female" });

            let first_name = if current_gender == "male" {
                male_names.choose(&mut rng).unwrap().to_string()
            } else {
                female_names.choose(&mut rng).unwrap().to_string()
            };

            let mut final_name = first_name;
            if rng.gen_bool(Self::NAME_SUFFIX_PROBABILITY) {
                let all_suffixes = vec!["儿", "然", "轩", "瑶", "豪", "菲"];
                let female_suffixes = vec!["儿", "瑶", "菲"];
                let male_suffixes = vec!["然", "轩", "豪"];

                let mut suffix = all_suffixes.choose(&mut rng).unwrap().to_string();
                if current_gender == "male" && female_suffixes.contains(&suffix.as_str()) {
                    suffix = male_suffixes.choose(&mut rng).unwrap().to_string();
                }
                final_name.push_str(&suffix);
            }

            names.push(format!("{}{}", surname, final_name));
        }

        names
    }
}

// 添加 html_to_text 配置结构体
#[derive(Debug, Default)]
pub struct HtmlToTextConfig {
    pub replace_images: bool,
    pub img_format: String,
    pub merge_empty_lines: bool,
    pub unescape_entities: bool,
    pub keep_line_breaks: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_data_processor() {
        // 测试数据处理功能
        let data = json!({
            "user": {
                "profile": {
                    "id": 1
                }
            }
        });

        let result =
            DataProcessor::filter_by_nested_values(&data, "user.profile.id", &[json!(1)], false)
                .unwrap();

        assert_eq!(result.len(), 1);
    }

    #[test]
    fn test_time_utils() {
        // 测试时间戳功能
        let ts = TimeUtils::current_timestamp(10);
        assert!(ts > 0);

        let formatted = TimeUtils::format_timestamp(Some(ts));
        assert!(!formatted.is_empty());
    }

    #[test]
    fn test_string_processor() {
        // 测试字符串处理
        let text = "hello";
        let result = StringProcessor::insert_zero_width(text);
        assert!(result.len() > text.len());
    }

    #[test]
    fn test_student_generator() {
        // 测试学生信息生成
        let classes = StudentDataGenerator::generate_class_names(5, (1, 6), true, true);
        assert_eq!(classes.len(), 5);

        let names = StudentDataGenerator::generate_student_names(10, Some("male"));
        assert_eq!(names.len(), 10);
    }
}
