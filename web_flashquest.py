import streamlit as st
import os
import docx
import PyPDF2
import pytesseract
from PIL import Image
import json
from groq import Groq, RateLimitError, APIError

# --- CẤU HÌNH ---
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==========================================
# PHẦN 1: LOGIC XỬ LÝ (BACKEND)
# ==========================================
class StudyMaterialProcessor:
    def __init__(self, selected_model_id):
        # --- API KEY ---
        api_key = "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" 
        
        # Lưu model ID được chọn từ giao diện
        self.model_id = selected_model_id

        try:
            self.client = Groq(api_key=api_key)
        except Exception as e:
            st.error(f"Lỗi kết nối Groq: {e}")
            self.client = None

    def extract_text_from_docx(self, file_path):
        try:
            doc = docx.Document(file_path)
            return '\n'.join([para.text for para in doc.paragraphs])
        except: return ""

    def extract_text_from_pdf(self, file_path):
        try:
            text = ""
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except: return ""

    def extract_text_from_image(self, file_path):
        try:
            img = Image.open(file_path)
            return pytesseract.image_to_string(img, lang='vie+eng')
        except: return ""

    def process_file(self, file_path):
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        raw_text = ""
        if ext == '.docx': raw_text = self.extract_text_from_docx(file_path)
        elif ext == '.pdf': raw_text = self.extract_text_from_pdf(file_path)
        elif ext in ['.jpg', '.jpeg', '.png']: raw_text = self.extract_text_from_image(file_path)
        
        if not raw_text.strip():
            return {"error_type": "DATA", "message": "Không đọc được nội dung text từ file này."}

        return self.analyze_with_ai(raw_text)

    def analyze_with_ai(self, text):
        if not self.client: return {"error_type": "CONFIG", "message": "Lỗi: Chưa có API Key"}
        
        try:
            # Prompt "Phủ kín nội dung"
            prompt = f"""
            Bạn là chuyên gia giáo dục. Nhiệm vụ: Tạo bộ câu hỏi trắc nghiệm phủ kín 100% nội dung tài liệu.
            Nội dung: "{text[:18000]}" 
            
            Yêu cầu JSON đầu ra:
            1. "tom_tat": Tóm tắt 3 phần (Mở, Thân, Kết) thật chi tiết.
            2. "goi_y_hoc": 5 phương pháp học.
            3. "tu_khoa": 10-15 từ khóa.
            4. "cau_hoi_quiz": Tạo số lượng câu hỏi KHÔNG GIỚI HẠN, tùy thuộc vào độ dài tài liệu.
               - Tài liệu dài phải có nhiều câu hỏi (20-50 câu) để rải đều kiến thức.
               - Đảm bảo học xong quiz là thuộc hết bài.
            
            Trả về JSON đúng mẫu:
            {{
                "tom_tat": "...",
                "goi_y_hoc": ["..."],
                "tu_khoa": ["..."],
                "cau_hoi_quiz": [{{"cau_hoi": "...", "dap_an": "..."}}]
            }}
            """

            # Gọi Groq API với Model được chọn
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý JSON. Chỉ trả về JSON hợp lệ."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model_id, # <-- Dùng model người dùng chọn
                temperature=0.5,
                max_tokens=7000, 
                response_format={"type": "json_object"} 
            )
            
            return json.loads(chat_completion.choices[0].message.content)

        # --- BẮT LỖI RATE LIMIT & QUOTA ---
        except RateLimitError:
            return {
                "error_type": "RATE_LIMIT", 
                "message": f"🚨 Model {self.model_id} đã HẾT LƯỢT hoặc QUÁ TẢI!\n👉 Vui lòng chọn Model khác ở thanh bên trái."
            }
        except APIError as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                return {
                    "error_type": "RATE_LIMIT", 
                    "message": f"🚨 Model {self.model_id} đang bận hoặc hết lượt!\n👉 Hãy đổi sang Model khác (ví dụ Llama 3.1)."
                }
            return {"error_type": "API", "message": f"Lỗi API: {str(e)}"}
        except Exception as e:
            return {"error_type": "UNKNOWN", "message": f"Lỗi không xác định: {str(e)}"}

# ==========================================
# PHẦN 2: GIAO DIỆN WEB
# ==========================================
def main():
    st.set_page_config(page_title="FlashQuest - AI Selector", page_icon="⚡", layout="wide")

    st.title("⚡ FlashQuest - Học tập siêu tốc")

    # --- THANH BÊN: CHỌN MODEL ---
    with st.sidebar:
        st.header("🧠 Cấu hình bộ não AI")
        
        # Danh sách Model tối ưu nhất từ ảnh bạn gửi
        model_options = {
            "🏆 Llama 3.3 (Thông minh nhất - 70B)": "llama-3.3-70b-versatile",
            "🚀 Llama 3.1 (Siêu tốc/Nhiều lượt - 8B)": "llama-3.1-8b-instant",
            "🤖 Qwen 2.5/3 (Logic tốt - 32B)": "qwen-2.5-32b", # Hoặc qwen/qwen3-32b nếu có
        }
        
        selected_name = st.selectbox(
            "Chọn mô hình phân tích:",
            options=list(model_options.keys()),
            index=0 # Mặc định chọn cái xịn nhất
        )
        
        # Lấy ID thực tế để gửi cho API
        selected_model_id = model_options[selected_name]
        
        st.info(f"Đang dùng: **{selected_model_id}**")
        st.caption("Mẹo: Nếu gặp lỗi hết lượt, hãy đổi sang dòng 'Siêu tốc' (Llama 3.1).")
        st.divider()
        st.write("Hướng dẫn:\n1. Tải tài liệu.\n2. Bấm Phân tích.\n3. Đổi model nếu cần.")

    # --- PHẦN CHÍNH ---
    uploaded_file = st.file_uploader("Tải lên tài liệu (Word, PDF, Ảnh)", type=['docx', 'pdf', 'jpg', 'png', 'jpeg'])

    if uploaded_file is not None:
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Đã nhận file: {uploaded_file.name}")

        if st.button("✨ Phân tích ngay"):
            # Truyền model ID vào bộ xử lý
            processor = StudyMaterialProcessor(selected_model_id)
            
            with st.spinner(f"AI ({selected_model_id}) đang đọc và soạn câu hỏi..."):
                result = processor.process_file(file_path)
            
            if os.path.exists(file_path): os.remove(file_path)

            # --- XỬ LÝ LỖI ---
            if "error_type" in result:
                err_type = result["error_type"]
                msg = result["message"]
                
                if err_type == "RATE_LIMIT":
                    st.error(msg, icon="🚫") # Hiện lỗi đỏ thật to
                    st.toast("Hãy đổi Model bên thanh trái!", icon="👈")
                else:
                    st.error(msg)
            
            # --- HIỂN THỊ KẾT QUẢ ---
            else:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("📝 Tóm tắt chuyên sâu")
                    st.info(result.get("tom_tat", ""))
                    
                    st.subheader("💡 Chiến lược học")
                    for gy in result.get("goi_y_hoc", []):
                        st.markdown(f"- {gy}")

                with col2:
                    st.subheader("🔑 Từ khóa")
                    for kw in result.get("tu_khoa", []):
                        st.button(f"🏷️ {kw}", use_container_width=True)

                st.divider()
                quiz_list = result.get("cau_hoi_quiz", [])
                st.subheader(f"❓ Ngân hàng câu hỏi ({len(quiz_list)} câu)")
                
                if not quiz_list:
                    st.warning("Không tạo được câu hỏi nào.")
                else:
                    for idx, q in enumerate(quiz_list, 1):
                        with st.expander(f"Câu {idx}: {q.get('cau_hoi')}"):
                            st.markdown(f"**Đáp án:** {q.get('dap_an')}")

if __name__ == "__main__":
    main()
