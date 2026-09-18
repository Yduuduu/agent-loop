from langchain_text_splitters import RecursiveCharacterTextSplitter

# 토크나이저 없이 문자 수로 근사(500~1000 토큰 ≈ 한글 기준 600~1200자 내외).
_CHUNK_SIZE_CHARS = 800
_CHUNK_OVERLAP_CHARS = 150


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE_CHARS,
        chunk_overlap=_CHUNK_OVERLAP_CHARS,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def split_text(text: str) -> list[str]:
    splitter = get_text_splitter()
    return splitter.split_text(text)
