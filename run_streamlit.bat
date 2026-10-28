@echo off
echo ========================================================
echo  Starting AI Database Assistant - Streamlit Frontend
echo  Target Database: ecommerce_db (Aiven MySQL 8.0+)
echo  Zero Authentication / Direct Multi-Page Access
echo ========================================================
streamlit run frontend/app.py --server.port 8501 --server.headless false
pause
