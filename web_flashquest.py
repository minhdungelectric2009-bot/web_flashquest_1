import streamlit as st
import os
import docx
import PyPDF2
# import pytesseract  <-- ĐÃ XÓA (Không cần nữa)
import base64  # <-- MỚI: Dùng để mã hóa ảnh gửi cho AI
from PIL import Image
import json
from groq import Groq, RateLimitError, APIError

# ==========================================
# PHẦN 1: LOGIC XỬ LÝ (BACKEND)
# ==========================================
class StudyMaterialProcessor:
    def __init__(self, selected_model_id):
        # Lấy API Key
        try:
            api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            st.error("⚠️ Chưa cấu hình GROQ_API_KEY trong Streamlit Secrets!")
            api_key = None
        
        self.model_id = selected_model_id

        if api_key:
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                st.error(f"Lỗi kết nối Groq: {e}")
                self.client = None
        else:
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

    # 👇 CODE MỚI: Dùng AI Vision thay cho Tesseract 👇
    def extract_text_from_image(self, file_path):
        if not self.client: return ""
        try:
            # 1. Mã hóa ảnh thành Base64 để gửi qua mạng
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            # 2. Gọi model Llama Vision (chuyên đọc ảnh)
            # Lưu ý: Luôn dùng model Vision cho bước này, bất kể người dùng chọn model nào ở ngoài
            vision_model = "llama-3.2-11b-vision-preview" 

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hãy trích xuất toàn bộ văn bản có trong hình ảnh này. Chỉ trả về nội dung văn bản, không thêm lời bình luận hay mô tả."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                },
                            },
                        ],
                    }
                ],
                model=vision_model,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Lỗi đọc ảnh bằng AI: {str(e)}"

    def process_file(self, file_path):
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        raw_text = ""
        if ext == '.docx': raw_text = self.extract_text_from_docx(file_path)
        elif ext == '.pdf': raw_text = self.extract_text_from_pdf(file_path)
        elif ext in ['.jpg', '.jpeg', '.png']: raw_text = self.extract_text_from_image(file_path)
        
        if not raw_text or not raw_text.strip():
            return {"error_type": "DATA", "message": "Không đọc được nội dung text từ file này."}

        # Sau khi có text, mới dùng model người dùng chọn để phân tích
        return self.analyze_with_ai(raw_text)

    def analyze_with_ai(self, text):
        if not self.client: return {"error_type": "CONFIG", "message": "Lỗi: Chưa cấu hình API Key."}
        
        try:
            prompt = f"""
            Bạn là chuyên gia giáo dục. Nhiệm vụ: Tạo bộ câu hỏi trắc nghiệm phủ kín 100% nội dung tài liệu.
            Nội dung: "{text[:20000]}" 
            
            Yêu cầu JSON đầu ra:
            1. "tom_tat": Tóm tắt 3 phần (Mở, Thân, Kết).
            2. "goi_y_hoc": 5 phương pháp học tập.
            3. "tu_khoa": 10-15 từ khóa.
            4. "cau_hoi_quiz": Tạo bộ câu hỏi (Không giới hạn, càng nhiều càng tốt).
            
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
                max_tokens=7500,
                response_format={"type": "json_object"} 
            )
            
            return json.loads(chat_completion.choices[0].message.content)

        except RateLimitError:
            return {"error_type": "RATE_LIMIT", "message": f"⛔ Model {self.model_id} hết lượt."}
        except APIError as e:
            return {"error_type": "API", "message": f"Lỗi API: {str(e)}"}
        except Exception as e:
            return {"error_type": "UNKNOWN", "message": f"Lỗi: {str(e)}"}

# ==========================================
# PHẦN 2: GIAO DIỆN WEB
# ==========================================
def main():
    st.set_page_config(page_title="FlashQuest - Smart Select", page_icon="⚡", layout="wide")
    st.title("⚡ FlashQuest - Học tập thông minh")

    with st.sidebar:
        st.header("🧠 Chọn Bộ Não AI")
        model_options = {
            "🏆 Llama 3.3 (Thông minh nhất - 70B)": "llama-3.3-70b-versatile",
            "🚀 Llama 3.1 (Siêu tốc - 8B)": "llama-3.1-8b-instant"
        }
        selected_name = st.selectbox("Mô hình xử lý:", options=list(model_options.keys()), index=0)
        selected_model_id = model_options[selected_name]
        
        st.info("📷 **Tính năng ảnh:** Tự động dùng Llama 3.2 Vision để đọc ảnh (Không cần cài phần mềm).")

    uploaded_file = st.file_uploader("Tải lên tài liệu", type=['docx', 'pdf', 'jpg', 'png', 'jpeg'])

    if uploaded_file is not None:
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Đã nhận file: {uploaded_file.name}")

        if st.button("✨ Phân tích ngay"):
            processor = StudyMaterialProcessor(selected_model_id)
            
            with st.spinner(f"AI đang đọc tài liệu và phân tích..."):
                result = processor.process_file(file_path)
            
            if os.path.exists(file_path): os.remove(file_path)

            if "error_type" in result:
                st.error(result["message"])
            else:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader("📝 Tóm tắt")
                    st.info(result.get("tom_tat", ""))
                    st.subheader("💡 Gợi ý học")
                    for gy in result.get("goi_y_hoc", []): st.markdown(f"- {gy}")
                with col2:
                    st.subheader("🔑 Từ khóa")
                    for kw in result.get("tu_khoa", []): st.button(f"🏷️ {kw}", use_container_width=True)
                
                st.divider()
                st.subheader("❓ Câu hỏi trắc nghiệm")
                for idx, q in enumerate(result.get("cau_hoi_quiz", []), 1):
                    with st.expander(f"Câu {idx}: {q.get('cau_hoi')}"):
                        st.markdown(f"**Đáp án:** {q.get('dap_an')}")

if __name__ == "__main__":
    main()
