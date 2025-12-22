import streamlit as st
import os
import docx
import PyPDF2
import pytesseract
from PIL import Image
import json
from groq import Groq

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
            # --- CẬP NHẬT PROMPT: QUÉT SẠCH NỘI DUNG (COVERAGE MODE) ---
            prompt = f"""
            Bạn là một chuyên gia giáo dục đang soạn ngân hàng câu hỏi thi.
            Nhiệm vụ: Phân tích tài liệu sau để tạo bộ câu hỏi trắc nghiệm bao phủ toàn diện 100% nội dung.
            
            Nội dung tài liệu: "{text[:15000]}" 
            
            Yêu cầu bắt buộc về đầu ra (JSON):
            1. "tom_tat": Tóm tắt nội dung tài liệu thành 3 phần (Mở bài, Thân bài chi tiết, Kết luận). Viết sâu và đầy đủ ý.
            2. "goi_y_hoc": Đưa ra các phương pháp học tập cụ thể.
            3. "tu_khoa": Liệt kê các từ khóa chuyên ngành quan trọng.
            4. "cau_hoi_quiz": Tạo bộ câu hỏi trắc nghiệm.
               - NGUYÊN TẮC VÀNG: KHÔNG GIỚI HẠN SỐ LƯỢNG CÂU HỎI.
               - Số lượng câu hỏi phải phụ thuộc hoàn toàn vào độ dài và độ phức tạp của tài liệu.
               - Tài liệu càng dài, càng nhiều kiến thức thì càng phải tạo nhiều câu hỏi. Có thể là 20, 30, 50 câu hoặc hơn.
               - Mục tiêu: Đảm bảo học sinh làm xong bộ câu hỏi này là nắm chắc chắn 100% kiến thức trong bài, không bỏ sót bất kỳ ý nhỏ nào.
               - Phân bổ: Câu hỏi phải rải đều từ dòng đầu tiên đến dòng cuối cùng.
            
            Cấu trúc JSON mẫu (Trả về đúng định dạng này):
            {{
                "tom_tat": "Nội dung tóm tắt...",
                "goi_y_hoc": ["Gợi ý 1", ...],
                "tu_khoa": ["Từ 1", "Từ 2", ...],
                "cau_hoi_quiz": [
                    {{"cau_hoi": "Câu hỏi 1?", "dap_an": "Đáp án 1"}},
                    {{"cau_hoi": "Câu hỏi 2?", "dap_an": "Đáp án 2"}},
                    ... (Tiếp tục tạo cho đến khi hết ý trong tài liệu)
                ]
            }}
            """

            # Gọi Groq API (Model Llama 3.3)
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý AI JSON mode. Hãy tạo càng nhiều câu hỏi càng tốt để phủ kín nội dung."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile", 
                temperature=0.5, # Giảm nhiệt độ để AI tập trung vào chi tiết chính xác
                max_tokens=7000, # Mở rộng tối đa bộ nhớ để chứa được hàng chục câu hỏi
                response_format={"type": "json_object"} 
            )
            
            return json.loads(chat_completion.choices[0].message.content)

        except Exception as e:
            return {"error": f"Lỗi AI: {str(e)}"}

# ==========================================
# PHẦN 2: GIAO DIỆN WEB (GIỮ NGUYÊN)
# ==========================================
def main():
    st.set_page_config(page_title="FlashQuest - Groq Edition", page_icon="⚡", layout="wide") 

    st.title("⚡ FlashQuest - Siêu tốc độ (Groq AI)")
    st.write("Tải lên tài liệu của bạn. AI sẽ tạo số lượng câu hỏi tương ứng để đảm bảo bạn học hết 100% kiến thức.")

    with st.sidebar:
        st.header("Trạng thái")
        st.success("Chế độ: Phủ kín nội dung (Comprehensive Coverage)")
        st.info("AI sẽ tự động dò tìm từng ý trong bài để đặt câu hỏi. Tài liệu dài sẽ có rất nhiều câu hỏi.")

    uploaded_file = st.file_uploader("Chọn tài liệu", type=['docx', 'pdf', 'jpg', 'png', 'jpeg'])

    if uploaded_file is not None:
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Đã tải lên: {uploaded_file.name}")

        if st.button("✨ Phân tích chi tiết"):
            processor = StudyMaterialProcessor()
            
            with st.spinner("🚀 Đang quét toàn bộ tài liệu để tạo bộ câu hỏi đầy đủ nhất..."):
                result = processor.process_file(file_path)
            
            if os.path.exists(file_path):
                os.remove(file_path)

            if "error" in result:
                st.error(result["error"])
            else:
                # --- Hiển thị kết quả ---
                st.subheader("📝 Tóm tắt chuyên sâu")
                st.info(result.get("tom_tat", ""))

                st.subheader("🔑 Từ khóa cốt lõi")
                keywords = result.get("tu_khoa", [])
                
                if keywords:
                    cols = st.columns(4) # Chia 4 cột cho thoáng
                    for i, kw in enumerate(keywords):
                        with cols[i % 4]:
                            st.button(f"🏷️ {kw}", key=f"kw_{i}", use_container_width=True)

                st.subheader("💡 Chiến lược học tập")
                for gy in result.get("goi_y_hoc", []):
                    st.markdown(f"- {gy}")

                # Hiển thị số lượng câu hỏi tìm được
                quiz_list = result.get("cau_hoi_quiz", [])
                st.divider()
                st.subheader(f"❓ Ngân hàng câu hỏi ({len(quiz_list)} câu)")
                st.caption("Số lượng câu hỏi được tạo dựa trên độ dài và chi tiết của tài liệu.")
                
                if not quiz_list:
                    st.warning("Không tạo được câu hỏi nào.")
                else:
                    for idx, q in enumerate(quiz_list, 1):
                        with st.expander(f"Câu {idx}: {q.get('cau_hoi')}"):
                            st.markdown(f"**Đáp án:** {q.get('dap_an')}")

if __name__ == "__main__":
    main()
