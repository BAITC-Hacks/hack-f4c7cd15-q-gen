"""Streamlit & Entry Application for MoneyGraph AML Copilot.

Includes tabs for:
1. 📊 Обзор графа и метрики
2. 🔍 Проверка участников (Dossier)
3. 🔗 Цепочки и маршруты
4. 🤖 AI-Ассистент («AML Graph Copilot»)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINANSE_DIR = ROOT / "finanse"
if str(FINANSE_DIR) not in sys.path:
    sys.path.insert(0, str(FINANSE_DIR))

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

from agent import ask_aml_agent, get_node_info, find_common_recipients, get_cluster_summary


def run_streamlit_app():
    if not STREAMLIT_AVAILABLE:
        print("Streamlit is not installed. To run Streamlit UI:")
        print("  pip install streamlit")
        print("  streamlit run app.py")
        print("\nДля основного веб-интерфейса используйте:")
        print("  python finanse/run.py --serve")
        return

    st.set_page_config(
        page_title="MoneyGraph AML Intelligence & Copilot",
        page_icon="◈",
        layout="wide"
    )

    st.title("◈ ПОТОК — Аналитика графа переводов & AML Copilot")
    st.markdown("Интеллектуальная система расследования транзакционных сетей в рамках HackAlem AI.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Обзор сети",
        "🔍 Карточки клиентов",
        "🔗 Цепочки переводов",
        "🤖 AI-Ассистент"
    ])

    with tab1:
        st.subheader("Сводные показатели выборки")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Клиентов в графе", "2 248")
        col2.metric("Связей (пар)", "3 119")
        col3.metric("Транзакций", "4 840")
        col4.metric("Общий оборот", "365,89 млн ₸")

    with tab2:
        st.subheader("Финансовый профиль участника")
        gid_input = st.text_input("Введите GID клиента:", value="100000003115284100")
        if st.button("Запросить профиль"):
            res = get_node_info(gid_input)
            st.json(res)

    with tab3:
        st.subheader("Поиск казначеев и аккумуляторов")
        gids_input = st.text_area("Введите GID клиентов (через запятую или перевод строки):", value="100000000331309100, 100000007629096100")
        if st.button("Найти общих получателей"):
            parsed_gids = [g.strip() for g in gids_input.replace("\n", ",").split(",") if g.strip()]
            res = find_common_recipients(parsed_gids)
            st.json(res)

    # Четвертая вкладка по ТЗ пользователя:
    with tab4:
        st.subheader("AML Graph Copilot")
        st.markdown("AI-ассистент комплаенс-офицера с доступом к инструментам анализа графа.")
        
        user_q = st.text_input(
            "Задайте вопрос по графу:",
            placeholder="Кто аккумулирует средства с клиентов 12345 и 67890?",
            value="Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?"
        )
        if st.button("Спросить"):
            with st.spinner("Анализирую связи графа..."):
                ans = ask_aml_agent(user_q)
                st.markdown(ans)


if __name__ == "__main__":
    if STREAMLIT_AVAILABLE:
        run_streamlit_app()
    else:
        # CLI Demo mode
        print("=" * 60)
        print("AML Graph Copilot CLI Launcher")
        print("=" * 60)
        q = "Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?"
        print(f"Пример запроса: {q}\n")
        print(ask_aml_agent(q))
