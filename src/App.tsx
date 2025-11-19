/** @format */

import React, { useState, useRef, useEffect } from "react"
import styled from "styled-components"
import GlobalStyle from "./styles/GlobalStyle"
import { diffLines, Change } from "diff"
import * as XLSX from "xlsx"

const Container = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
`

const Panel = styled.div<{ width: string }>`
  width: ${(props) => props.width};
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e0e0e0;
  overflow: hidden;
  background: #1e1e1e;
  color: #d4d4d4;
`

const EditorContainer = styled.div`
  flex: 1;
  overflow: auto;
  position: relative;
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 14px;
  line-height: 1.5;
`

const LineNumber = styled.div<{ isDeleted?: boolean; isAdded?: boolean; isModified?: boolean }>`
  display: inline-block;
  width: 50px;
  padding: 0 10px;
  text-align: right;
  color: #858585;
  user-select: none;
  background: ${(props) => {
    if (props.isDeleted) return "#4b1818"
    if (props.isAdded) return "#373d29"
    if (props.isModified) return "#5a4e1f"
    return "transparent"
  }};
  border-right: 1px solid #2d2d2d;
`

const LineContent = styled.div<{ isDeleted?: boolean; isAdded?: boolean; isModified?: boolean }>`
  display: inline-block;
  padding: 0 10px;
  white-space: pre;
  background: ${(props) => {
    if (props.isDeleted) return "#4b1818"
    if (props.isAdded) return "#373d29"
    if (props.isModified) return "#5a4e1f"
    return "transparent"
  }};
  color: ${(props) => {
    if (props.isDeleted) return "#f48771"
    if (props.isAdded) return "#89d185"
    return "#d4d4d4"
  }};
  width: calc(100% - 50px);
`

const Line = styled.div<{ isDeleted?: boolean; isAdded?: boolean; isModified?: boolean; ref?: any }>`
  display: flex;
  min-height: 22px;
  border-left: 3px solid
    ${(props) => {
      if (props.isDeleted) return "#f48771"
      if (props.isAdded) return "#89d185"
      if (props.isModified) return "#cca700"
      return "transparent"
    }};
  &:hover {
    background: rgba(255, 255, 255, 0.05);
  }
`

const Button = styled.button`
  padding: 10px 20px;
  margin: 10px;
  background: #0e639c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;

  &:hover {
    background: #1177bb;
  }

  &:active {
    background: #0a4d75;
  }

  &:disabled {
    background: #3c3c3c;
    cursor: not-allowed;
  }
`

const ButtonContainer = styled.div`
  display: flex;
  justify-content: center;
  padding: 10px;
  background: #252526;
  border-top: 1px solid #3c3c3c;
`

const ChangesList = styled.div`
  flex: 1;
  overflow: auto;
  padding: 10px;
`

const ChangeItem = styled.div<{ type: "added" | "removed" | "modified" }>`
  padding: 8px;
  margin-bottom: 8px;
  border-radius: 4px;
  cursor: pointer;
  background: ${(props) => {
    if (props.type === "added") return "#373d29"
    if (props.type === "removed") return "#4b1818"
    return "#5a4e1f"
  }};
  border-left: 3px solid
    ${(props) => {
      if (props.type === "added") return "#89d185"
      if (props.type === "removed") return "#f48771"
      return "#cca700"
    }};
  transition: background 0.2s;

  &:hover {
    background: ${(props) => {
      if (props.type === "added") return "#4a5233"
      if (props.type === "removed") return "#5d1f1f"
      return "#6b5f25"
    }};
  }
`

const ChangeType = styled.span<{ type: "added" | "removed" | "modified" }>`
  font-weight: bold;
  color: ${(props) => {
    if (props.type === "added") return "#89d185"
    if (props.type === "removed") return "#f48771"
    return "#cca700"
  }};
  margin-right: 8px;
`

const ChangeText = styled.div`
  font-size: 12px;
  color: #d4d4d4;
  margin-top: 4px;
  white-space: pre-wrap;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
`

const FileInput = styled.input`
  display: none;
`

interface DiffLine {
  lineNumber: number
  content: string
  type: "added" | "removed" | "modified" | "unchanged"
  oldLineNumber?: number
  newLineNumber?: number
}

interface ChangeSummary {
  type: "added" | "removed" | "modified"
  lineNumber: number
  content: string
  oldContent?: string
  oldLineNumber?: number
  newLineNumber?: number
}

function App() {
  const [leftText, setLeftText] = useState<string>("")
  const [rightText, setRightText] = useState<string>("")
  const [leftDiffLines, setLeftDiffLines] = useState<DiffLine[]>([])
  const [rightDiffLines, setRightDiffLines] = useState<DiffLine[]>([])
  const [changes, setChanges] = useState<ChangeSummary[]>([])
  const leftFileInputRef = useRef<HTMLInputElement>(null)
  const rightFileInputRef = useRef<HTMLInputElement>(null)
  const leftEditorRef = useRef<HTMLDivElement>(null)
  const rightEditorRef = useRef<HTMLDivElement>(null)

  const processDiff = (oldText: string, newText: string) => {
    const diff = diffLines(oldText, newText)
    const leftLines: DiffLine[] = []
    const rightLines: DiffLine[] = []
    const changeSummaries: ChangeSummary[] = []

    let oldLineNum = 1
    let newLineNum = 1
    let i = 0

    // 먼저 수정된 줄을 감지하기 위해 diff 배열을 분석
    while (i < diff.length) {
      const current = diff[i]
      const next = diff[i + 1]

      // 삭제 후 바로 추가가 오는 경우 = 수정
      if (current.removed && next && next.added) {
        const removedLines = current.value.split("\n").filter((line) => line !== "")
        const addedLines = next.value.split("\n").filter((line) => line !== "")
        const maxLines = Math.max(removedLines.length, addedLines.length)

        for (let j = 0; j < maxLines; j++) {
          const removedLine = removedLines[j]
          const addedLine = addedLines[j]

          if (removedLine !== undefined && addedLine !== undefined) {
            // 둘 다 있는 경우 = 수정
            leftLines.push({
              lineNumber: oldLineNum++,
              content: removedLine,
              type: "modified",
              oldLineNumber: oldLineNum - 1,
            })
            rightLines.push({
              lineNumber: newLineNum++,
              content: addedLine,
              type: "modified",
              newLineNumber: newLineNum - 1,
            })
            changeSummaries.push({
              type: "modified",
              lineNumber: newLineNum - 1,
              content: addedLine,
              oldContent: removedLine,
              oldLineNumber: oldLineNum - 1,
              newLineNumber: newLineNum - 1,
            })
          } else if (removedLine !== undefined) {
            // 삭제만 있는 경우
            leftLines.push({
              lineNumber: oldLineNum++,
              content: removedLine,
              type: "removed",
              oldLineNumber: oldLineNum - 1,
            })
            changeSummaries.push({
              type: "removed",
              lineNumber: oldLineNum - 1,
              content: removedLine,
              oldLineNumber: oldLineNum - 1,
            })
          } else if (addedLine !== undefined) {
            // 추가만 있는 경우
            rightLines.push({
              lineNumber: newLineNum++,
              content: addedLine,
              type: "added",
              newLineNumber: newLineNum - 1,
            })
            changeSummaries.push({
              type: "added",
              lineNumber: newLineNum - 1,
              content: addedLine,
              newLineNumber: newLineNum - 1,
            })
          }
        }
        i += 2 // removed와 added 둘 다 처리했으므로 2 증가
      } else if (current.removed) {
        // 삭제만 있는 경우
        const lines = current.value.split("\n").filter((line) => line !== "")
        lines.forEach((line) => {
          leftLines.push({
            lineNumber: oldLineNum++,
            content: line,
            type: "removed",
            oldLineNumber: oldLineNum - 1,
          })
          changeSummaries.push({
            type: "removed",
            lineNumber: oldLineNum - 1,
            content: line,
            oldLineNumber: oldLineNum - 1,
          })
        })
        i++
      } else if (current.added) {
        // 추가만 있는 경우
        const lines = current.value.split("\n").filter((line) => line !== "")
        lines.forEach((line) => {
          rightLines.push({
            lineNumber: newLineNum++,
            content: line,
            type: "added",
            newLineNumber: newLineNum - 1,
          })
          changeSummaries.push({
            type: "added",
            lineNumber: newLineNum - 1,
            content: line,
            newLineNumber: newLineNum - 1,
          })
        })
        i++
      } else {
        // 변경되지 않은 줄들
        const lines = current.value.split("\n").filter((line) => line !== "")
        lines.forEach((line) => {
          leftLines.push({
            lineNumber: oldLineNum++,
            content: line,
            type: "unchanged",
            oldLineNumber: oldLineNum - 1,
          })
          rightLines.push({
            lineNumber: newLineNum++,
            content: line,
            type: "unchanged",
            newLineNumber: newLineNum - 1,
          })
        })
        i++
      }
    }

    setLeftDiffLines(leftLines)
    setRightDiffLines(rightLines)
    setChanges(changeSummaries)
  }

  const handleFileUpload = (side: "left" | "right", event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      if (side === "left") {
        setLeftText(text)
      } else {
        setRightText(text)
      }

      // 두 파일이 모두 로드되면 diff 계산
      if (side === "left" && rightText) {
        processDiff(text, rightText)
      } else if (side === "right" && leftText) {
        processDiff(leftText, text)
      }
    }
    reader.readAsText(file)
  }

  useEffect(() => {
    if (leftText && rightText) {
      processDiff(leftText, rightText)
    }
  }, [leftText, rightText])

  const scrollToLine = (lineNumber: number, side: "left" | "right") => {
    const editor = side === "left" ? leftEditorRef.current : rightEditorRef.current
    if (!editor) return

    const lineElement = editor.querySelector(`[data-line-number="${lineNumber}"]`)
    if (lineElement) {
      lineElement.scrollIntoView({ behavior: "smooth", block: "center" })
      // 하이라이트 효과
      lineElement.classList.add("highlight")
      setTimeout(() => {
        lineElement.classList.remove("highlight")
      }, 2000)
    }
  }

  const handleChangeClick = (change: ChangeSummary) => {
    if (change.oldLineNumber) {
      scrollToLine(change.oldLineNumber, "left")
    }
    if (change.newLineNumber) {
      scrollToLine(change.newLineNumber, "right")
    }
  }

  const exportToExcel = () => {
    if (changes.length === 0) {
      alert("변경사항이 없습니다.")
      return
    }

    const wsData = [
      ["타입", "이전 줄 번호", "이후 줄 번호", "이전 내용", "이후 내용"],
      ...changes.map((change) => [
        change.type === "added" ? "추가" : change.type === "removed" ? "삭제" : "수정",
        change.oldLineNumber || "",
        change.newLineNumber || "",
        change.oldContent || change.content || "",
        change.content || "",
      ]),
    ]

    const ws = XLSX.utils.aoa_to_sheet(wsData)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, "변경사항")

    XLSX.writeFile(wb, "문서_비교_결과.xlsx")
  }

  return (
    <>
      <GlobalStyle />
      <Container>
        <Panel width="40%">
          <EditorContainer ref={leftEditorRef}>
            {leftDiffLines.map((line, index) => (
              <Line key={`left-${index}`} isDeleted={line.type === "removed"} isAdded={line.type === "added"} isModified={line.type === "modified"} data-line-number={line.lineNumber}>
                <LineNumber isDeleted={line.type === "removed"} isAdded={line.type === "added"} isModified={line.type === "modified"}>
                  {line.type === "added" ? "" : line.lineNumber}
                </LineNumber>
                <LineContent isDeleted={line.type === "removed"} isAdded={line.type === "added"} isModified={line.type === "modified"}>
                  {line.content || " "}
                </LineContent>
              </Line>
            ))}
          </EditorContainer>
          <ButtonContainer>
            <FileInput ref={leftFileInputRef} type="file" accept=".txt,.md,.js,.ts,.jsx,.tsx,.json,.xml,.html,.css" onChange={(e) => handleFileUpload("left", e)} />
            <Button onClick={() => leftFileInputRef.current?.click()}>문서 업로드</Button>
          </ButtonContainer>
        </Panel>

        <Panel width="40%">
          <EditorContainer ref={rightEditorRef}>
            {rightDiffLines.map((line, index) => (
              <Line key={`right-${index}`} isDeleted={line.type === "removed"} isAdded={line.type === "added"} isModified={line.type === "modified"} data-line-number={line.lineNumber}>
                <LineNumber isDeleted={line.type === "removed"} isAdded={line.type === "added"} isModified={line.type === "modified"}>
                  {line.type === "removed" ? "" : line.lineNumber}
                </LineNumber>
                <LineContent isDeleted={line.type === "removed"} isAdded={line.type === "added"} isModified={line.type === "modified"}>
                  {line.content || " "}
                </LineContent>
              </Line>
            ))}
          </EditorContainer>
          <ButtonContainer>
            <FileInput ref={rightFileInputRef} type="file" accept=".txt,.md,.js,.ts,.jsx,.tsx,.json,.xml,.html,.css" onChange={(e) => handleFileUpload("right", e)} />
            <Button onClick={() => rightFileInputRef.current?.click()}>문서 업로드</Button>
          </ButtonContainer>
        </Panel>

        <Panel width="20%">
          <ChangesList>
            <h3 style={{ padding: "10px", margin: 0, borderBottom: "1px solid #3c3c3c" }}>변경사항</h3>
            {changes.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "#858585" }}>문서를 업로드하여 비교하세요</div>
            ) : (
              changes.map((change, index) => (
                <ChangeItem key={index} type={change.type} onClick={() => handleChangeClick(change)}>
                  <ChangeType type={change.type}>{change.type === "added" ? "추가" : change.type === "removed" ? "삭제" : "수정"}</ChangeType>
                  <div style={{ fontSize: "11px", color: "#858585" }}>
                    {change.oldLineNumber && `이전: ${change.oldLineNumber}`}
                    {change.oldLineNumber && change.newLineNumber && " / "}
                    {change.newLineNumber && `이후: ${change.newLineNumber}`}
                  </div>
                  {change.type === "modified" && change.oldContent && <ChangeText style={{ color: "#f48771", textDecoration: "line-through" }}>{change.oldContent}</ChangeText>}
                  <ChangeText>{change.content}</ChangeText>
                </ChangeItem>
              ))
            )}
          </ChangesList>
          <ButtonContainer>
            <Button onClick={exportToExcel} disabled={changes.length === 0}>
              엑셀(.xlsx) 저장
            </Button>
          </ButtonContainer>
        </Panel>
      </Container>
    </>
  )
}

export default App
