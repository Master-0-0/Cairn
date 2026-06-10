#!/usr/bin/env python3
"""
Cairn 文件上传工具 - Web 服务

提供网页界面用于:
  1. 输入项目 ID
  2. 上传附件
  3. 自动查找对应 Docker 容器并拷贝文件
"""

import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_PORT = int(os.environ.get("UPLOAD_PORT", "9000"))


HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cairn 文件上传</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f1f5f9; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .card { background: #fff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); padding: 32px; width: 100%; max-width: 480px; }
  h1 { font-size: 20px; font-weight: 700; color: #0f172a; margin-bottom: 4px; }
  .sub { font-size: 13px; color: #94a3b8; margin-bottom: 24px; }
  label { display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px; }
  input[type="text"] { width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 10px; font-size: 14px; outline: none; transition: border-color .2s; }
  input[type="text"]:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
  .file-area { border: 2px dashed #e2e8f0; border-radius: 12px; padding: 28px; text-align: center; cursor: pointer; transition: all .2s; margin-top: 4px; }
  .file-area:hover, .file-area.dragover { border-color: #6366f1; background: #f8fafc; }
  .file-area p { font-size: 13px; color: #94a3b8; }
  .file-area .name { color: #6366f1; font-weight: 600; margin-top: 6px; display: none; }
  input[type="file"] { display: none; }
  button { width: 100%; padding: 12px; background: #6366f1; color: #fff; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 20px; transition: background .2s; }
  button:hover { background: #4f46e5; }
  button:disabled { background: #cbd5e1; cursor: not-allowed; }
  .msg { margin-top: 16px; padding: 12px 16px; border-radius: 10px; font-size: 13px; display: none; white-space: pre-wrap; word-break: break-all; }
  .msg.success { display: block; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
  .msg.error { display: block; background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
  .tips { margin-top: 20px; padding: 14px 16px; background: #f8fafc; border-radius: 10px; font-size: 12px; color: #64748b; line-height: 1.7; }
</style>
</head>
<body>
<div class="card">
  <h1>Cairn 文件上传</h1>
  <p class="sub">上传代码附件到项目容器</p>

  <form id="form" enctype="multipart/form-data">
    <label for="pid">项目 ID</label>
    <input type="text" id="pid" name="project_id" placeholder="例如: proj_027" required>

    <label style="margin-top:16px">附件</label>
    <div class="file-area" id="dropZone">
      <p>点击选择文件或拖拽到此处</p>
      <p class="name" id="fileName"></p>
      <input type="file" id="fileInput" name="file" required>
    </div>

    <button type="submit" id="submitBtn">上传到容器</button>
  </form>

  <div class="msg" id="msg"></div>

  <div class="tips">
    <strong>工作原理:</strong><br>
    1. 输入项目 ID（Web UI 中创建的项目编号）<br>
    2. 选择要上传的文件或目录（目录需先打包）<br>
    3. 自动查找 <code>cairn-dispatch-{项目ID}</code> 容器并拷贝
  </div>
</div>

<script>
const form = document.getElementById('form');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const submitBtn = document.getElementById('submitBtn');
const msg = document.getElementById('msg');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    fileName.textContent = e.dataTransfer.files[0].name;
    fileName.style.display = 'block';
  }
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    fileName.textContent = fileInput.files[0].name;
    fileName.style.display = 'block';
  }
});

form.addEventListener('submit', async e => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = '处理中...';
  msg.className = 'msg';
  msg.style.display = 'none';

  const fd = new FormData(form);
  try {
    const res = await fetch('/upload', { method: 'POST', body: fd });
    const data = await res.json();
    msg.className = 'msg ' + (data.ok ? 'success' : 'error');
    msg.textContent = data.message;
    msg.style.display = 'block';
  } catch (err) {
    msg.className = 'msg error';
    msg.textContent = '请求失败: ' + err.message;
    msg.style.display = 'block';
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = '上传到容器';
  }
});
</script>
</body>
</html>"""


def parse_multipart(body: bytes, boundary: str) -> dict[str, tuple[str, bytes, str | None]]:
    """解析 multipart/form-data，返回 {name: (filename, data, content_type)}"""
    result = {}
    boundary_bytes = boundary.encode()
    parts = body.split(b"--" + boundary_bytes)
    for part in parts:
        if part in (b"--\r\n", b"--", b""):
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_raw = part[:header_end].decode(errors="replace")
        content = part[header_end + 4 :]
        if content.endswith(b"\r\n"):
            content = content[:-2]

        name = None
        filename = None
        content_type = None
        for line in headers_raw.split("\r\n"):
            line_lower = line.lower()
            if line_lower.startswith("content-disposition:"):
                for chunk in line.split(";"):
                    chunk = chunk.strip()
                    if chunk.startswith('name="'):
                        name = chunk[6:-1]
                    elif chunk.startswith('filename="'):
                        filename = chunk[10:-1]
            elif line_lower.startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()

        if name:
            result[name] = (filename or "", content, content_type)
    return result


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self.send_error(404)

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode())

    def _handle_upload(self):
        self._responded = False
        try:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._json({"ok": False, "message": "需要 multipart/form-data"})
                return

            # 提取 boundary
            boundary = None
            for part in content_type.split(";"):
                part = part.strip()
                if part.startswith("boundary="):
                    boundary = part[9:]
                    if boundary.startswith('"') and boundary.endswith('"'):
                        boundary = boundary[1:-1]
                    break

            if not boundary:
                self._json({"ok": False, "message": "无法解析 boundary"})
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            fields = parse_multipart(body, boundary)

            project_id = fields.get("project_id", ("", b"", None))[1].decode().strip()
            file_field = fields.get("file")
            if not project_id:
                self._json({"ok": False, "message": "请输入项目 ID"})
                return
            if not file_field or not file_field[1]:
                self._json({"ok": False, "message": "请选择文件"})
                return

            filename = file_field[0] or "uploaded_file"
            file_data = file_field[1]

            # 1. 保存到 ./tmp/ 目录，保留原始文件名和后缀
            tmp_dir = os.path.join(os.getcwd(), "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, filename)

            with open(tmp_path, "wb") as f:
                f.write(file_data)

            print(f"[上传] 项目={project_id}, 文件={filename}, 临时路径={tmp_path}")
            msg_lines = [f"1. 上传成功: {tmp_path}"]

            # 2. 查找容器
            container_name = f"cairn-dispatch-{project_id}"
            print(f"[查找容器] 正在查找容器: {container_name}")
            try:
                found = subprocess.run(
                    ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
                    capture_output=True, text=True, timeout=10,
                )
                if container_name not in found.stdout:
                    print(f"[查找容器] 未找到容器: {container_name}")
                    msg_lines.append(f"2. 错误: 未找到容器 {container_name}")
                    self._json({"ok": False, "message": "\n".join(msg_lines)})
                    return
                print(f"[查找容器] 找到容器: {container_name}")
                msg_lines.append(f"2. 找到容器: {container_name}")
            except Exception as e:
                print(f"[查找容器] 查找失败: {e}")
                msg_lines.append(f"2. 错误: 查找容器失败 - {e}")
                self._json({"ok": False, "message": "\n".join(msg_lines)})
                return

            # 3. docker cp 拷贝
            dest = f"{container_name}:/home/{filename}"
            print(f"[拷贝] 正在拷贝: {tmp_path} -> {dest}")
            try:
                result = subprocess.run(
                    ["docker", "cp", tmp_path, dest],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    print(f"[拷贝] 拷贝成功: {dest}")
                    msg_lines.append(f"3. 拷贝成功: {dest}")
                else:
                    err = result.stderr.strip()
                    print(f"[拷贝] 拷贝失败: {err}")
                    msg_lines.append(f"3. 拷贝失败: {err}")
                    self._json({"ok": False, "message": "\n".join(msg_lines)})
                    return
            except Exception as e:
                print(f"[拷贝] 拷贝失败: {e}")
                msg_lines.append(f"3. 拷贝失败: {e}")
                self._json({"ok": False, "message": "\n".join(msg_lines)})
                return

            self._json({"ok": True, "message": "\n".join(msg_lines)})

        except Exception as e:
            if not self._responded:
                self._json({"ok": False, "message": f"服务端错误: {str(e)}"})

    def _json(self, data: dict):
        import json
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._responded = True

    def log_message(self, format, *args):
        # 简化日志
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))


def main():
    server = HTTPServer(("0.0.0.0", UPLOAD_PORT), RequestHandler)
    print(f"Cairn 文件上传服务已启动: http://localhost:{UPLOAD_PORT}")
    print(f"按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
