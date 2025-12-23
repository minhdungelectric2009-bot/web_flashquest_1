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
        # --- API KEY (DÁN TRỰC TIẾP) ---
        api_key = "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" 
        
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
            # Prompt: Quét sạch 100% nội dung
            prompt = f"""
            Bạn là chuyên gia giáo dục. Nhiệm vụ: Tạo bộ câu hỏi trắc nghiệm phủ kín 100% nội dung tài liệu.
            Nội dung: "{text[:20000]}" 
            
            Yêu cầu JSON đầu ra:
            1. "tom_tat": Tóm tắt 3 phần (Mở, Thân, Kết) thật chi tiết, sâu sắc.
            2. "goi_y_hoc": 5 phương pháp học tập cụ thể.
            3. "tu_khoa": 10-15 từ khóa chuyên ngành.
            4. "cau_hoi_quiz": Tạo bộ câu hỏi KHÔNG GIỚI HẠN SỐ LƯỢNG.
               - Nguyên tắc: Tài liệu có bao nhiêu ý thì có bấy nhiêu câu hỏi.
               - Tài liệu dài phải có nhiều câu (20, 30, 50 câu...).
               - Phải rải đều câu hỏi từ đầu đến cuối văn bản.
            
            Trả về JSON đúng mẫu:
            {{
                "tom_tat": "...",
                "goi_y_hoc": ["..."],
                "tu_khoa": ["..."],
                "cau_hoi_quiz": [{{"cau_hoi": "...", "dap_an": "..."}}]
            }}
            """

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý JSON. Chỉ trả về JSON hợp lệ."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model_id, 
                temperature=0.5,
                max_tokens=7500, # Bộ nhớ cực lớn để chứa nhiều câu hỏi
                response_format={"type": "json_object"} 
            )
            
            return json.loads(chat_completion.choices[0].message.content)

        # --- XỬ LÝ LỖI HẾT LIMIT (QUAN TRỌNG) ---
        except RateLimitError:
            return {
                "error_type": "RATE_LIMIT", 
                "message": f"⛔ MODEL {self.model_id} ĐÃ HẾT LƯỢT TRONG NGÀY!\n\n👉 Vui lòng nhìn sang thanh bên trái và chọn Model khác (ví dụ: Llama 3.1) để tiếp tục."
            }
        except APIError as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                return {
                    "error_type": "RATE_LIMIT", 
                    "message": f"⛔ MODEL {self.model_id} ĐANG QUÁ TẢI!\n\n👉 Hãy đổi sang Model khác ngay lập tức."
                }
            return {"error_type": "API", "message": f"Lỗi API: {str(e)}"}
        except Exception as e:
            return {"error_type": "UNKNOWN", "message": f"Lỗi không xác định: {str(e)}"}

# ==========================================
# PHẦN 2: GIAO DIỆN WEB
# ==========================================
def main():
    st.set_page_config(page_title="FlashQuest - Smart Select", page_icon="⚡", layout="wide")

    st.title("⚡ FlashQuest - Học tập thông minh")

    # --- THANH BÊN: CHỌN MODEL (Đã lọc) ---
    with st.sidebar:
        st.header("🧠 Chọn Bộ Não AI")
        
        # Chỉ giữ lại 2 model hoạt động tốt nhất
        model_options = {
            "🏆 Llama 3.3 (Thông minh nhất - 70B)": "llama-3.3-70b-versatile",
            "🚀 Llama 3.1 (Siêu tốc/Không giới hạn - 8B)": "llama-3.1-8b-instant"
        }
        
        selected_name = st.selectbox(
            "Mô hình xử lý:",
            options=list(model_options.keys()),
            index=0 # Mặc định chọn cái xịn nhất
        )
        
        selected_model_id = model_options[selected_name]
        
        # Hiển thị trạng thái Model
        if "70b" in selected_model_id:
            st.info("✅ **Đang dùng:** Model chất lượng cao.\n⚠️ **Lưu ý:** Giới hạn khoảng 1000 lượt/ngày.")
        else:
            st.success("✅ **Đang dùng:** Model siêu tốc.\n🛡️ **Ưu điểm:** Hầu như không bao giờ hết lượt.")
            
        st.divider()
        st.write("**Hướng dẫn đổi AI:**")
        st.caption("Nếu thấy báo lỗi màu đỏ 'Hết lượt', hãy đổi ngay sang dòng Llama 3.1 ở trên.")

    # --- PHẦN CHÍNH ---
    uploaded_file = st.file_uploader("Tải lên tài liệu (Word, PDF, Ảnh)", type=['docx', 'pdf', 'jpg', 'png', 'jpeg'])

    if uploaded_file is not None:
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Đã nhận file: {uploaded_file.name}")

        if st.button("✨ Phân tích ngay"):
            processor = StudyMaterialProcessor(selected_model_id)
            
            with st.spinner(f"AI ({selected_name}) đang quét toàn bộ kiến thức..."):
                result = processor.process_file(file_path)
            
            if os.path.exists(file_path): os.remove(file_path)

            # --- HIỂN THỊ LỖI NẾU CÓ ---
            if "error_type" in result:
                err_type = result["error_type"]
                msg = result["message"]
                
                if err_type == "RATE_LIMIT":
                    # Hiện thông báo lỗi cực lớn để học sinh chú ý đổi model
                    st.error(msg, icon="🚫")
                    with st.sidebar:
                        st.error("🚨 HẾT LIMIT! Đổi Model ngay tại đây ⬆️")
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
                
                # Hiển thị tiêu đề ngân hàng câu hỏi
                st.subheader(f"❓ Ngân hàng câu hỏi ({len(quiz_list)} câu)")
                if len(quiz_list) > 20:
                    st.caption("🔥 Tài liệu rất chi tiết! AI đã tạo ra số lượng lớn câu hỏi để bao phủ toàn bộ kiến thức.")
                
                if not quiz_list:
                    st.warning("Không tạo được câu hỏi nào.")
                else:
                    for idx, q in enumerate(quiz_list, 1):
                        with st.expander(f"Câu {idx}: {q.get('cau_hoi')}"):
                            st.markdown(f"**Đáp án:** {q.get('dap_an')}")

if __name__ == "__main__":
    main()
