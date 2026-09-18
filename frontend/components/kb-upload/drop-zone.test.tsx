import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DropZone } from "./drop-zone";

describe("DropZone", () => {
  it("accepts a valid PDF selected via the file input", async () => {
    const user = userEvent.setup();
    const onFilesAccepted = vi.fn();
    render(<DropZone onFilesAccepted={onFilesAccepted} />);

    const file = new File([new Uint8Array(10)], "policy.pdf", { type: "application/pdf" });
    const input = screen.getByLabelText("PDF 파일 선택");
    await user.upload(input, file);

    expect(onFilesAccepted).toHaveBeenCalledWith([file]);
    expect(screen.queryByText(/PDF 파일만/)).not.toBeInTheDocument();
  });

  it("shows a validation error and does not accept a non-PDF file", async () => {
    // input의 accept="application/pdf"를 실제 브라우저 파일 선택창처럼 적용하면
    // user-event가 non-PDF를 아예 선택 목록에서 걸러버려 우리 검증 로직까지
    // 도달하지 못한다. 드래그앤드롭(브라우저가 accept를 강제하지 않는 경로)으로
    // 잘못된 파일이 들어오는 경우를 검증하는 것이 이 테스트의 목적이므로 끈다.
    const user = userEvent.setup({ applyAccept: false });
    const onFilesAccepted = vi.fn();
    render(<DropZone onFilesAccepted={onFilesAccepted} />);

    const file = new File(["hi"], "notes.txt", { type: "text/plain" });
    const input = screen.getByLabelText("PDF 파일 선택");
    await user.upload(input, file);

    expect(onFilesAccepted).not.toHaveBeenCalled();
    expect(screen.getByText(/PDF 파일만/)).toBeInTheDocument();
  });

  it("opens the file picker when the drop zone is clicked", async () => {
    const user = userEvent.setup();
    render(<DropZone onFilesAccepted={vi.fn()} />);

    const input = screen.getByLabelText("PDF 파일 선택") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    await user.click(screen.getByTestId("kb-drop-zone"));

    expect(clickSpy).toHaveBeenCalled();
  });
});
