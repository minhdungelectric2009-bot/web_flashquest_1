import streamlit as st
import os
import docx
import PyPDF2
import pytesseract
from PIL import Image
import json
from groq import Groq  # <-- Thay đổi: Dùng thư viện Groq

# --- CẤU HÌNH ---
# 1. Cấu hình Tesseract (Cho Windows local)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==========================================
# PHẦN 1: LOGIC XỬ LÝ (BACKEND - GROQ)
# ==========================================
class StudyMaterialProcessor:
    def __init__(self):
            # --- CẤU HÌNH API KEY (DÁN TRỰC TIẾP) ---
            # Tôi đã dán sẵn key của bạn vào đây rồi, không cần st.secrets nữa
            api_key = "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" 
    
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                st.error(f"Lỗi kết nối Groq: {e}")
                self.client = None

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
            if not self.client: return {"error": "Lỗi: Chưa có API Key"}
            
            try:
                # --- CẬP NHẬT PROMPT: Yêu cầu viết dài và chi tiết hơn ---
                prompt = f"""
                Bạn là một giảng viên đại học tâm huyết và chuyên sâu.
                Nhiệm vụ: Phân tích tài liệu học tập sau đây để soạn giáo án ôn thi chi tiết.
                
                Nội dung tài liệu: "{text[:8000]}" 
                
                Yêu cầu bắt buộc về đầu ra (JSON):
                1. "tom_tat": Viết một đoạn văn tóm tắt CHI TIẾT, đầy đủ các ý chính, độ dài khoảng 150-200 từ. KHÔNG được viết sơ sài.
                2. "goi_y_hoc": Đưa ra 4-5 gợi ý hành động cụ thể để nắm vững kiến thức này.
                3. "tu_khoa": Liệt kê ít nhất 8-10 từ khóa chuyên ngành quan trọng nhất trong bài.
                4. "cau_hoi_quiz": Tạo ra ít nhất 5 câu hỏi ôn tập (kèm đáp án đúng).
                
                Cấu trúc JSON mẫu (bắt buộc trả về đúng định dạng này):
                {{
                    "tom_tat": "Nội dung tóm tắt chi tiết...",
                    "goi_y_hoc": ["Gợi ý 1", "Gợi ý 2", "Gợi ý 3", "Gợi ý 4"],
                    "tu_khoa": ["Từ khóa 1", "Từ khóa 2", "Từ khóa 3", "Từ khóa 4", "Từ khóa 5", "Từ khóa 6", "Từ khóa 7", "Từ khóa 8"],
                    "cau_hoi_quiz": [
                        {{"cau_hoi": "Câu hỏi 1?", "dap_an": "Đáp án 1"}},
                        {{"cau_hoi": "Câu hỏi 2?", "dap_an": "Đáp án 2"}},
                        {{"cau_hoi": "Câu hỏi 3?", "dap_an": "Đáp án 3"}},
                        {{"cau_hoi": "Câu hỏi 4?", "dap_an": "Đáp án 4"}},
                        {{"cau_hoi": "Câu hỏi 5?", "dap_an": "Đáp án 5"}}
                    ]
                }}
                """
    
               # Gọi Groq API (Dùng model Llama 3.3 mới nhất)
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Bạn là trợ lý AI chuyên về giáo dục, luôn trả về định dạng JSON hợp lệ."},
                        {"role": "user", "content": prompt}
                    ],
                    model="llama-3.3-70b-versatile", 
                    temperature=0.7, # Tăng độ sáng tạo lên một chút để viết dài hơn
                    max_tokens=2000, # Cho phép câu trả lời dài hơn
                    response_format={"type": "json_object"} 
                )
            
                return json.loads(chat_completion.choices[0].message.content)
    
            except Exception as e:
                return {"error": f"Lỗi AI: {str(e)}"}

# ==========================================
# PHẦN 2: GIAO DIỆN WEB (GIỮ NGUYÊN)
# ==========================================
def main():
    st.set_page_config(page_title="FlashQuest - Groq Edition", page_icon="⚡")

    st.title("⚡ FlashQuest - Siêu tốc độ (Groq AI)")
    st.write("Tải lên tài liệu của bạn (Word, PDF, Ảnh) để AI phân tích và tạo bài học.")

    with st.sidebar:
        st.header("Hướng dẫn")
        st.info("1. Chọn file tài liệu.\n2. Bấm nút Phân tích.\n3. Nhận kết quả ngay lập tức.")
        st.success("Đang chạy trên nền tảng Groq (Llama 3)")

    uploaded_file = st.file_uploader("Chọn tài liệu", type=['docx', 'pdf', 'jpg', 'png', 'jpeg'])

    if uploaded_file is not None:
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Đã tải lên: {uploaded_file.name}")

        if st.button("✨ Phân tích ngay"):
            processor = StudyMaterialProcessor()
            
            # Đổi spinner cho ngầu hơn
            with st.spinner("🚀 Đang kích hoạt động cơ Llama 3 siêu tốc..."):
                result = processor.process_file(file_path)
            
            if os.path.exists(file_path):
                os.remove(file_path)

            if "error" in result:
                st.error(result["error"])
            else:
                # --- Phần hiển thị này giữ nguyên như code cũ của bạn ---
                st.subheader("📝 Tóm tắt bài học")
                st.info(result.get("tom_tat", ""))

                st.subheader("🔑 Từ khóa quan trọng")
                keywords = result.get("tu_khoa", [])
                
                if keywords:
                    cols = st.columns(3)
                    for i, kw in enumerate(keywords):
                        with cols[i % 3]:
                            st.button(f"🏷️ {kw}", key=f"kw_{i}", use_container_width=True)

                st.subheader("💡 Gợi ý học tập")
                for gy in result.get("goi_y_hoc", []):
                    st.markdown(f"- {gy}")

                st.subheader("❓ Câu hỏi ôn tập")
                for idx, q in enumerate(result.get("cau_hoi_quiz", []), 1):
                    with st.expander(f"Câu hỏi {idx}: {q.get('cau_hoi')}"):
                        st.markdown(f"**Đáp án:** {q.get('dap_an')}")
                        st.balloons() 

if __name__ == "__main__":
    main()




