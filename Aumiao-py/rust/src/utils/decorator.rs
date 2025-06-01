use log::{error, warn};
use std::future::Future;
use std::pin::Pin;
use std::sync::Once;
use std::time::Duration;
use tokio::time::sleep;

pub trait Singleton {
    fn instance() -> &'static Self;
}

#[macro_export]
macro_rules! singleton {
    ($t:ty) => {
        impl $t {
            pub fn instance() -> &'static Self {
                static mut INSTANCE: Option<$t> = None;
                static ONCE: Once = Once::new();

                unsafe {
                    ONCE.call_once(|| {
                        INSTANCE = Some(Self::new());
                    });
                    INSTANCE.as_ref().unwrap()
                }
            }
        }
    };
}

pub use singleton;

#[derive(Debug)]
pub enum RetryError {
    MaxRetriesReached(String),
    InvalidConfig(String),
}

impl std::fmt::Display for RetryError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RetryError::MaxRetriesReached(msg) => write!(f, "Max retries reached: {}", msg),
            RetryError::InvalidConfig(msg) => write!(f, "Invalid configuration: {}", msg),
        }
    }
}

impl std::error::Error for RetryError {}

pub struct RetryConfig {
    pub retries: u32,
    pub delay: Duration,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            retries: 3,
            delay: Duration::from_secs(1),
        }
    }
}

// 重试装饰器
pub async fn with_retry<F, Fut, T, E>(f: F, config: Option<RetryConfig>) -> Result<T, RetryError>
where
    F: Fn() -> Fut,
    Fut: Future<Output = Result<T, E>>,
    E: std::fmt::Debug,
{
    let config = config.unwrap_or_default();

    if config.retries < 1 {
        return Err(RetryError::InvalidConfig(
            "Retries must be at least 1".into(),
        ));
    }

    let mut last_error = None;
    for i in 0..config.retries {
        match f().await {
            Ok(value) => return Ok(value),
            Err(e) => {
                last_error = Some(e);
                if i < config.retries - 1 {
                    warn!("Attempt {} failed, retrying...", i + 1);
                    sleep(config.delay).await;
                }
            }
        }
    }

    Err(RetryError::MaxRetriesReached(format!(
        "Failed after {} retries. Last error: {:?}",
        config.retries, last_error
    )))
}

// 错误跳过装饰器
pub trait SkipOnError<T> {
    fn skip_on_error(self) -> Option<T>;
}

impl<T, E: std::fmt::Debug> SkipOnError<T> for Result<T, E> {
    fn skip_on_error(self) -> Option<T> {
        match self {
            Ok(value) => Some(value),
            Err(e) => {
                error!("Error occurred: {:?}. Skipping this iteration.", e);
                None
            }
        }
    }
}

// 生成器装饰器
pub struct Chunked<I> {
    inner: I,
    chunk_size: usize,
}

impl<I: Iterator> Iterator for Chunked<I> {
    type Item = Vec<I::Item>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut chunk = Vec::with_capacity(self.chunk_size);
        for _ in 0..self.chunk_size {
            match self.inner.next() {
                Some(item) => chunk.push(item),
                None if chunk.is_empty() => return None,
                None => break,
            }
        }
        Some(chunk)
    }
}

pub trait ChunkedIterator: Iterator + Sized {
    fn chunks(self, chunk_size: usize) -> Chunked<Self> {
        Chunked {
            inner: self,
            chunk_size,
        }
    }
}

impl<T: Iterator> ChunkedIterator for T {}

// 延迟加载属性宏
#[macro_export]
macro_rules! lazy_property {
    ($vis:vis $name:ident: $t:ty = $init:expr) => {
        $vis fn $name(&self) -> &$t {
            static ONCE: Once = Once::new();
            static mut VALUE: Option<$t> = None;

            unsafe {
                ONCE.call_once(|| {
                    VALUE = Some($init);
                });
                VALUE.as_ref().unwrap()
            }
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};

    #[tokio::test]
    async fn test_retry() {
        let counter = AtomicU32::new(0);
        let result = with_retry(
            || async {
                let count = counter.fetch_add(1, Ordering::SeqCst);
                if count < 2 { Err("Not ready") } else { Ok(42) }
            },
            None,
        )
        .await;

        assert!(result.is_ok());
        assert_eq!(counter.load(Ordering::SeqCst), 3);
    }

    #[test]
    fn test_skip_on_error() {
        let result: Result<i32, &str> = Ok(42);
        assert_eq!(result.skip_on_error(), Some(42));

        let result: Result<i32, &str> = Err("error");
        assert_eq!(result.skip_on_error(), None);
    }

    #[test]
    fn test_chunked_iterator() {
        let numbers = vec![1, 2, 3, 4, 5];
        let chunks: Vec<Vec<i32>> = numbers.into_iter().chunks(2).collect();
        assert_eq!(chunks, vec![vec![1, 2], vec![3, 4], vec![5]]);
    }

    struct TestStruct {
        counter: AtomicU32,
    }

    impl TestStruct {
        lazy_property!(pub value: u32 = {
            self.counter.fetch_add(1, Ordering::SeqCst);
            42
        });
    }

    #[test]
    fn test_lazy_property() {
        let test = TestStruct {
            counter: AtomicU32::new(0),
        };

        assert_eq!(*test.value(), 42);
        assert_eq!(*test.value(), 42);
        assert_eq!(test.counter.load(Ordering::SeqCst), 1);
    }
}
