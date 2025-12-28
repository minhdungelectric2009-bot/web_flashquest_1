import streamlit as st
import os
import docx
import PyPDF2
import base64
import json
import time
import random
from PIL import Image
from groq import Groq

# ==========================================
# CẤU HÌNH & CSS (TÍCH HỢP TỪ STYLE.CSS CỦA BẠN)
# ==========================================
st.set_page_config(page_title="FlashQuest: Chronicles of Knowledge", page_icon="🔥", layout="wide")

# CSS tùy chỉnh - Mang hiệu ứng LỬA từ file style.css vào Streamlit
st.markdown("""
<style>
    /* Nhập font game */
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Roboto:wght@400;700&display=swap');

    /* Hiệu ứng Lửa Rung (từ file style.css) */
    @keyframes flameWiggle {
        0% { transform: rotate(-2deg) scale(1); }
        50% { transform: rotate(1deg) scale(1.05); }
        100% { transform: rotate(-2deg) scale(1); }
    }
    
    @keyframes auraFlow {
        0% { text-shadow: 0 0 20px #ff4500, 0 0 40px #ff8c00; }
        50% { text-shadow: 0 0 35px #ffd700, 0 0 70px #ff69b4; }
        100% { text-shadow: 0 0 20px #ff4500, 0 0 40px #ff8c00; }
    }

    .fire-streak {
        font-size: 100px;
        text-align: center;
        cursor: pointer;
        user-select: none;
        animation: flameWiggle 3s infinite ease-in-out, auraFlow 4s infinite alternate;
        margin: 0 auto;
        display: block;
        width: 150px;
    }

    .streak-count {
        font-family: 'Press Start 2P', cursive;
        text-align: center;
        font-size: 24px;
        background: linear-gradient(90deg, #ff8a00, #ff0058);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: -20px;
    }

    /* Thẻ bài RPG */
    .rpg-card {
        background-color: #1E1E1E;
        border: 2px solid #333;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .rpg-card:hover {
        transform: scale(1.02);
        border-color: #ff8a00;
    }

    /* Thanh máu/XP */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #00b09b, #96c93d);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# PHẦN 1: QUẢN LÝ TRẠNG THÁI (SESSION STATE - DATABASE GIẢ LẬP)
# ==========================================
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "name": "Người Tập Sự",
        "level": 1,
        "xp": 0,
        "max_xp": 100,
        "class": None, # Scholar, Warrior, Guardian
        "streak_days": 0,
        "last_study_date": None,
        "gold": 0
    }

if 'pet_info' not in st.session_state:
    st.session_state.pet_info = {
        "name": "Trứng Rồng",
        "stage": 0, # 0: Trứng, 1: Bé, 2: Trưởng thành, 3: Thần thú
        "health": 100,
        "emotion": "Ngủ đông"
    }

if 'inventory' not in st.session_state:
    st.session_state.inventory = []

if 'current_quest' not in st.session_state:
    st.session_state.current_quest = None

if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = []

# ==========================================
# PHẦN 2: BACKEND AI (FLASHQUEST CORE)
# ==========================================
class FlashQuestAI:
    def __init__(self):
        try:
            api_key = st.secrets["GROQ_API_KEY"]
            self.client = Groq(api_key=api_key)
            self.model_vision = "llama-3.2-11b-vision-preview"
            self.model_text = "llama-3.3-70b-versatile"
        except Exception:
            st.error("⚠️ Chưa cấu hình GROQ_API_KEY trong Secrets!")
            self.client = None

    def process_image(self, file_path):
        """Đọc ảnh bằng Llama Vision"""
        if not self.client: return ""
        try:
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            chat = self.client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Trích xuất toàn bộ văn bản trong ảnh này. Chỉ trả về text."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }],
                model=self.model_vision
            )
            return chat.choices[0].message.content
        except Exception as e:
            return f"Lỗi Vision: {str(e)}"

    def analyze_learning_material(self, text, user_class):
        """Phân tích nội dung và tạo Nhiệm vụ RPG"""
        if not self.client: return None
        
        # Tùy biến prompt theo Class nhân vật
        bonus_instruction = ""
        if user_class == "Học Giả":
            bonus_instruction = "Tạo câu hỏi sâu sắc, yêu cầu tư duy logic cao. Tăng XP thưởng."
        elif user_class == "Chiến Binh":
            bonus_instruction = "Tạo nhiều câu hỏi phản xạ nhanh. Thời gian ngắn."
        elif user_class == "Hộ Vệ":
            bonus_instruction = "Tạo câu hỏi củng cố nền tảng, độ khó vừa phải nhưng bao quát."

        prompt = f"""
        Bạn là Game Master của FlashQuest. Người chơi thuộc hệ: {user_class}.
        Nội dung học: "{text[:15000]}"
        {bonus_instruction}
        
        Hãy tạo dữ liệu JSON cho màn chơi "Tháp Kiến Thức":
        1. "tom_tat": Tóm tắt nội dung như một cốt truyện game (Ngắn gọn).
        2. "monsters": Tạo 5-10 câu hỏi trắc nghiệm dưới dạng Quái Vật. 
           - "name": Tên quái vật (liên quan kiến thức, vd: Slime Đạo Hàm).
           - "question": Câu hỏi.
           - "options": ["A...", "B...", "C...", "D..."].
           - "answer": Đáp án đúng (chữ cái).
           - "hp": Máu của quái (Độ khó 1-100).
           - "xp_reward": Kinh nghiệm nhận được.
        3. "boss": 1 Câu hỏi trùm cuối cực khó.
        4. "next_suggestion": Gợi ý 1 chủ đề liên quan để học vào ngày mai (Dựa trên Knowledge Graph).
        
        Output JSON Only.
        """
        try:
            chat = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Bạn là JSON Game Master. Chỉ trả về JSON hợp lệ."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model_text,
                temperature=0.6,
                response_format={"type": "json_object"}
            )
            return json.loads(chat.choices[0].message.content)
        except Exception as e:
            st.error(f"Lỗi AI: {e}")
            return None

# ==========================================
# PHẦN 3: GIAO DIỆN & LOGIC GAME
# ==========================================

def update_xp(amount):
    """Cộng XP và xử lý lên cấp"""
    profile = st.session_state.user_profile
    profile['xp'] += amount
    
    # Hiệu ứng nổ pháo hoa khi nhận XP
    if amount > 0:
        st.toast(f"⚔️ +{amount} XP!", icon="✨")

    if profile['xp'] >= profile['max_xp']:
        profile['level'] += 1
        profile['xp'] -= profile['max_xp']
        profile['max_xp'] = int(profile['max_xp'] * 1.2)
        st.balloons()
        st.success(f"🎉 CHÚC MỪNG! BẠN ĐÃ THĂNG CẤP {profile['level']}!")
        
        # Pet tiến hóa theo cấp độ
        if profile['level'] == 5:
            st.session_state.pet_info['stage'] = 1
            st.session_state.pet_info['name'] = "Rồng Lửa Nhỏ"
            st.session_state.pet_info['emotion'] = "Tò mò"
        elif profile['level'] == 10:
            st.session_state.pet_info['stage'] = 2
            st.session_state.pet_info['name'] = "Chiến Binh Rồng"

def render_sidebar():
    """Thanh bên hiển thị thông tin nhân vật và Pet"""
    with st.sidebar:
        st.header("🛡️ Hồ Sơ Hiệp Sĩ")
        
        # Chọn Class nếu chưa có
        if not st.session_state.user_profile['class']:
            st.warning("Bạn chưa chọn Nghề!")
            role = st.selectbox("Chọn Nghề Nghiệp:", ["Học Giả (The Scholar)", "Chiến Binh (The Warrior)", "Hộ Vệ (The Guardian)"])
            if st.button("Xác Nhận Nghề"):
                st.session_state.user_profile['class'] = role.split(" ")[0]
                st.rerun()
        else:
            p = st.session_state.user_profile
            st.subheader(f"Level {p['level']} {p['name']}")
            st.caption(f"Class: {p['class']}")
            st.progress(p['xp'] / p['max_xp'], text=f"XP: {p['xp']}/{p['max_xp']}")
            st.write(f"💰 Vàng: {p['gold']}")

        st.divider()
        
        # Hiển thị Pet
        pet = st.session_state.pet_info
        st.header("🐉 Linh Thú")
        
        pet_emoji = "🥚"
        if pet['stage'] == 1: pet_emoji = "🦎"
        elif pet['stage'] == 2: pet_emoji = "🐉"
        
        col_pet1, col_pet2 = st.columns([1, 2])
        with col_pet1:
            st.markdown(f"<div style='font-size: 40px; text-align: center;'>{pet_emoji}</div>", unsafe_allow_html=True)
        with col_pet2:
            st.write(f"**{pet['name']}**")
            st.caption(f"Tâm trạng: {pet['emotion']}")
            
        # Máu của Pet (gắn liền với Streak)
        st.write("Sinh Mệnh (Dựa trên Streak):")
        st.progress(pet['health'] / 100)

def render_streak_hub():
    """Giao diện chính: Lửa Streak và Nhiệm vụ"""
    st.markdown("<h1 style='text-align: center;'>🔥 Lò Luyện Tri Thức</h1>", unsafe_allow_html=True)
    
    # Hiển thị Lửa (Dựa trên style.css)
    streak = st.session_state.user_profile['streak_days']
    
    fire_class = "fire-streak"
    if streak == 0:
        st.markdown("""
        <div style='text-align: center; filter: grayscale(100%); opacity: 0.5;' class='fire-streak'>🔥</div>
        <div class='streak-count'>Chuỗi đã tắt...</div>
        <p style='text-align: center; color: #888;'>Hãy hoàn thành 1 bài học để thắp lại lửa!</p>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class='fire-streak'>🔥</div>
        <div class='streak-count'>{streak} NGÀY LIÊN TIẾP</div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Gợi ý bài học từ AI (Giả lập AI Recommendation)
    st.subheader("📜 Nhiệm Vụ Hàng Ngày (Daily Quest)")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Nhiệm vụ chính:** Đạt 500 XP hôm nay.\n\n*Phần thưởng: +50 Vàng, Hồi máu Pet*")
    with col2:
        if 'next_suggestion' in st.session_state and st.session_state.next_suggestion:
            st.success(f"**💡 AI Đề xuất:** {st.session_state.next_suggestion}\n\n*Lý do: Bạn đang yếu phần này.*")
        else:
            st.warning("Chưa có dữ liệu học tập. Hãy nạp kiến thức mới!")

def render_the_forge(ai_processor):
    """Nạp kiến thức (Upload & Vision)"""
    st.header("⚒️ The Forge (Rèn Luyện)")
    st.caption("Nạp tài liệu để AI tạo ra quái vật và thử thách.")
    
    uploaded_file = st.file_uploader("Chọn Sách Sức Mạnh (PDF/Ảnh/Word)", type=['docx', 'pdf', 'jpg', 'png'])
    
    if uploaded_file and st.button("🔮 Triệu Hồi Thử Thách"):
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("AI đang đọc thần chú..."):
            # 1. Xử lý file
            raw_text = ""
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext in ['.jpg', '.jpeg', '.png']:
                raw_text = ai_processor.process_image(file_path)
            elif ext == '.docx':
                doc = docx.Document(file_path)
                raw_text = '\n'.join([p.text for p in doc.paragraphs])
            elif ext == '.pdf':
                reader = PyPDF2.PdfReader(file_path)
                for page in reader.pages: raw_text += page.extract_text()
            
            # 2. AI tạo Game
            if raw_text:
                game_data = ai_processor.analyze_learning_material(raw_text, st.session_state.user_profile['class'])
                
                if game_data:
                    st.session_state.current_quest = game_data
                    st.session_state.quiz_data = game_data.get('monsters', [])
                    # Lưu gợi ý cho ngày mai
                    if 'next_suggestion' in game_data:
                        st.session_state.next_suggestion = game_data['next_suggestion']
                    
                    st.success("Triệu hồi thành công! Hãy vào 'Đấu Trường' để chiến đấu.")
            
            if os.path.exists(file_path): os.remove(file_path)

def render_arena():
    """Đấu trường trắc nghiệm"""
    st.header("⚔️ Đấu Trường Tri Thức")
    
    quest = st.session_state.current_quest
    if not quest:
        st.info("Chưa có kẻ thù nào. Hãy vào 'The Forge' để tạo màn chơi.")
        return

    st.markdown(f"**Cốt truyện:** {quest.get('tom_tat', '')}")
    
    monsters = st.session_state.quiz_data
    
    # Form chiến đấu
    with st.form("battle_form"):
        total_xp_gain = 0
        correct_count = 0
        
        for idx, monster in enumerate(monsters):
            st.markdown(f"""
            <div class='rpg-card'>
                <h4>👾 Lv.{monster.get('hp', 10)} {monster['name']}</h4>
                <p>{monster['question']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            user_ans = st.radio(f"Chọn đòn đánh (Câu {idx+1}):", monster['options'], key=f"q_{idx}")
            st.divider()
        
        submitted = st.form_submit_button("🔥 TUNG CHIÊU!")
        
        if submitted:
            st.write("--- KẾT QUẢ TRẬN ĐẤU ---")
            for idx, monster in enumerate(monsters):
                key = f"q_{idx}"
                user_choice = st.session_state.get(key)
                # Lấy ký tự đầu (A, B, C...)
                choice_char = user_choice.split('.')[0] if user_choice else ""
                
                if choice_char == monster['answer']:
                    st.success(f"✅ Bạn đã tiêu diệt {monster['name']}! (+{monster['xp_reward']} XP)")
                    total_xp_gain += monster['xp_reward']
                    correct_count += 1
                else:
                    st.error(f"❌ Bạn bị {monster['name']} phản đòn! (Đáp án: {monster['answer']})")
                    st.session_state.pet_info['health'] -= 5
            
            # Cập nhật kết quả
            update_xp(total_xp_gain)
            
            # Logic Streak
            if correct_count > 0:
                today = time.strftime("%Y-%m-%d")
                if st.session_state.user_profile['last_study_date'] != today:
                    st.session_state.user_profile['streak_days'] += 1
                    st.session_state.user_profile['last_study_date'] = today
                    st.session_state.pet_info['health'] = min(100, st.session_state.pet_info['health'] + 20)
                    st.toast("🔥 CHUỖI ĐÃ ĐƯỢC THẮP SÁNG!", icon="🔥")

def render_guild():
    """Mô phỏng tính năng Bang Hội"""
    st.header("🏰 Bang Hội & Xã Hội")
    
    st.info("Tính năng đang phát triển trong Giai đoạn 2 (Social).")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Lò Luyện Bang Hội")
        st.markdown("""
        <div style='text-align: center; font-size: 50px;'>🌋</div>
        <p style='text-align: center;'>Lửa Bang Hội đang cháy: <b>80%</b></p>
        <button style='width: 100%;'>🔥 Góp củi (Học bài)</button>
        """, unsafe_allow_html=True)
        
    with col2:
        st.subheader("Boss Thế Giới")
        st.warning("⚠️ RỒNG IELTS ĐANG TẤN CÔNG!")
        st.progress(0.4, text="HP Boss: 4000/10000")
        st.button("⚔️ Tham gia Raid Boss (Yêu cầu Level 5)")

# ==========================================
# MAIN APP
# ==========================================
def main():
    if 'user_profile' not in st.session_state:
        st.session_state.user_profile['class'] = None

    render_sidebar()
    
    # Navigation Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 Hành Trình (Hub)", "⚒️ Rèn Luyện (Forge)", "⚔️ Đấu Trường (Arena)", "🏰 Bang Hội (Guild)"])
    
    ai = FlashQuestAI()
    
    with tab1:
        render_streak_hub()
    
    with tab2:
        render_the_forge(ai)
        
    with tab3:
        render_arena()
        
    with tab4:
        render_guild()

if __name__ == "__main__":
    main()
