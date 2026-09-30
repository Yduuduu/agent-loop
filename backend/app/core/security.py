"""업로드 파일 처리 공통 보안 유틸리티(Phase 6.2)."""

from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """클라이언트가 보낸 파일명에서 경로 조작(path traversal) 요소를 제거한다.

    `Path(name).name`은 "../../etc/passwd"나 "/etc/passwd" 같은 입력에서도
    마지막 구성요소만 남기므로(각각 "passwd"), 그 결과를 디렉터리 밖으로
    벗어나지 않는 파일명으로만 사용한다. 결과가 비어있거나 "."/".."이면
    업로드 자체를 거부하도록 빈 문자열을 반환한다.
    """
    name = Path(filename).name
    if name in ("", ".", ".."):
        return ""
    return name
