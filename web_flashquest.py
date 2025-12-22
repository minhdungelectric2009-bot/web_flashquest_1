import streamlit as st
import os
import docx
import PyPDF2
import pytesseract
from PIL import Image
import google.generativeai as genai
import json

# --- CẤU HÌNH ---
# 1. Cấu hình Tesseract (Lưu ý: Đường dẫn này chỉ chạy trên máy local của bạn)
# Nếu đưa lên server thật thì cần cấu hình khác, nhưng chạy trên máy bạn thì giữ nguyên.
import shutil
# Chỉ cấu hình đường dẫn nếu chạy trên Windows (máy cá nhân)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 2. API KEY (Lấy từ Secrets của Streamlit)
try:
    # Thử lấy từ Secrets (khi chạy trên Web)
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    # Nếu chạy trên máy cá nhân không có Secrets thì dùng key dự phòng (hoặc để trống)
    # Khuyên bạn nên tạo file .streamlit/secrets.toml trên máy local nếu muốn chạy thử
    GOOGLE_API_KEY = "AIzaSyAZg8aSX11fbmzLy6KGekkWuv9aLzdkZYo"

# ==========================================
# PHẦN 1: LOGIC XỬ LÝ (GIỮ NGUYÊN)
# ==========================================
class StudyMaterialProcessor:
    def __init__(self):
        if GOOGLE_API_KEY == "DÁN_KEY_CỦA_BẠN_VÀO_ĐÂY":
            st.error("⚠️ CẢNH BÁO: Bạn chưa điền API Key thật!")
        else:
            genai.configure(api_key=GOOGLE_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite') 

    def extract_text_from_docx(self, file_path):
        try:
            doc = docx.Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except Exception: return ""

    def extract_text_from_pdf(self, file_path):
        try:
            text = ""
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception: return ""

    def extract_text_from_image(self, file_path):
        try:
            img = Image.open(file_path)
            return pytesseract.image_to_string(img, lang='vie+eng')
        except Exception: return ""

    def process_file(self, file_path):
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower()
        
        raw_text = ""
        if file_extension == '.docx':
            raw_text = self.extract_text_from_docx(file_path)
        elif file_extension == '.pdf':
            raw_text = self.extract_text_from_pdf(file_path)
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            raw_text = self.extract_text_from_image(file_path)
        
        if not raw_text.strip():
            return {"error": "Không đọc được nội dung text từ file này."}

        return self.analyze_with_ai(raw_text)

    def analyze_with_ai(self, text):
        try:
            prompt = f"""
            Bạn là trợ lý ảo cho game giáo dục FlashQuest. 
            Nhiệm vụ: Phân tích nội dung tài liệu học tập sau đây.
            Nội dung: "{text[:4000]}" 
            
            Yêu cầu trả về kết quả JSON chuẩn (không markdown):
            {{
                "tom_tat": "Tóm tắt ngắn gọn 2-3 câu",
                "goi_y_hoc": ["Gợi ý 1", "Gợi ý 2"],
                "tu_khoa": ["Từ khóa 1", "Từ khóa 2", "Từ khóa 3"],
                "cau_hoi_quiz": [
                    {{"cau_hoi": "Câu hỏi trắc nghiệm?", "dap_an": "Đáp án đúng"}}
                ]
            }}
            Chỉ trả về JSON.
            """
            response = self.model.generate_content(prompt)
            ai_text = response.text.strip()
            if ai_text.startswith("```json"): ai_text = ai_text[7:]
            if ai_text.endswith("```"): ai_text = ai_text[:-3]
            return json.loads(ai_text)
        except Exception as e:
            return {"error": f"Lỗi AI: {str(e)}"}

# ==========================================
# PHẦN 2: GIAO DIỆN WEB (STREAMLIT)
# ==========================================
def main():
    # Cấu hình trang web
    st.set_page_config(page_title="FlashQuest AI", page_icon="🚀")

    # Header
    st.title("🚀 FlashQuest AI - Trợ lý học tập")
# -------------------------------------------
    st.write("Tải lên tài liệu của bạn (Word, PDF, Ảnh) để AI phân tích và tạo bài học.")

    # Sidebar (Thanh bên trái)
    with st.sidebar:
        st.header("Hướng dẫn")
        st.info("1. Chọn file tài liệu.\n2. Bấm nút Phân tích.\n3. Nhận kết quả tóm tắt và câu hỏi.")
        st.warning("Lưu ý: File ảnh cần cài Tesseract OCR trên máy chủ.")

    # Widget tải file
    uploaded_file = st.file_uploader("Chọn tài liệu", type=['docx', 'pdf', 'jpg', 'png', 'jpeg'])

    if uploaded_file is not None:
        # Streamlit lưu file trên RAM, cần lưu tạm xuống ổ đĩa để hàm cũ đọc được
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Đã tải lên: {uploaded_file.name}")

        # Nút bấm
        if st.button("✨ Phân tích ngay"):
            processor = StudyMaterialProcessor()
            
            with st.spinner("AI đang đọc tài liệu và suy nghĩ..."):
                # Gọi hàm xử lý
                result = processor.process_file(file_path)
            
            # Xóa file tạm sau khi xong
            os.remove(file_path)

            # Hiển thị kết quả
            if "error" in result:
                st.error(result["error"])
            else:
                # 1. Tóm tắt
                st.subheader("📝 Tóm tắt bài học")
                st.info(result.get("tom_tat", ""))

                # 2. Từ khóa (Dùng columns để hiển thị ngang)
                st.subheader("🔑 Từ khóa quan trọng")
                keywords = result.get("tu_khoa", [])
                
                if keywords:
                    # Tạo 3 cột cố định để từ khóa luôn có đủ chỗ hiển thị
                    cols = st.columns(3)
                    for i, kw in enumerate(keywords):
                        # Logic chia đều: Từ thứ 1 vào cột 1, từ thứ 2 vào cột 2...
                        with cols[i % 3]:
                           # use_container_width=True giúp nút tự co giãn cho đẹp
                            st.button(f"🏷️ {kw}", key=f"kw_{i}", use_container_width=True)

                # 3. Gợi ý học
                st.subheader("💡 Gợi ý học tập")
                for gy in result.get("goi_y_hoc", []):
                    st.markdown(f"- {gy}")

                # 4. Quiz (Dùng expander để ẩn đáp án)
                st.subheader("❓ Câu hỏi ôn tập")
                for idx, q in enumerate(result.get("cau_hoi_quiz", []), 1):
                    with st.expander(f"Câu hỏi {idx}: {q.get('cau_hoi')}"):
                        st.markdown(f"**Đáp án:** {q.get('dap_an')}")
                        st.balloons() # Hiệu ứng vui vẻ khi mở đáp án

if __name__ == "__main__":

    main()















