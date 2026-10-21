#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("not a valid zip archive: {0}")]
    Zip(#[from] zip::result::ZipError),
    #[error("io error reading skin archive: {0}")]
    Io(#[from] std::io::Error),
    #[error("main.bmp is missing — every classic skin needs a main window background")]
    MissingMainBmp,
    #[error("{name}: not a BMP file (missing 'BM' magic)")]
    NotABmp { name: String },
    #[error("{name}: unsupported BMP variant (bpp={bpp}, compression={compression})")]
    UnsupportedBmp { name: String, bpp: u16, compression: u32 },
    #[error("{name}: truncated or corrupt BMP data")]
    TruncatedBmp { name: String },
}
