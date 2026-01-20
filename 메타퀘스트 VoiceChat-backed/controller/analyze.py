# controller/analyze.py
# Unity -> 백엔드 서버용

from fastapi import APIRouter, UploadFile, File, HTTPException
from groq import Groq
import os


router = APIRouter(
    prefix="/analyze",
    tags=["video analyze"]
)


client = Groq(
    api_key="grok_api_key"   # 테스트용
    # api_key=os.getenv("GROQ_API_KEY")   # render 대시보드에 적은 groq api 키 가져오기
)




@router.post("/")
async def analyze_voice(file: UploadFile = File(...)) :

    ### STT 과정
    try:
        transcript = client.audio.transcriptions.create(
            file=(file.filename, await file.read()),
            model="whisper-large-v3",
            temperature=0,   # 모델의 창의성. 보통 음성인식에선 0을 사용한다고 함. (0~1)
            response_format="text"   # text 형식으로 반환
            # prompt="This audio is likely to be Korean or English."  # 언어 자동 인식 기능이 있지만 혹시라도 한국어 인식 못 할까봐. 
        )
    
    except Exception as e :
        raise HTTPException(status_code=500, detail=f"STT Error : {e}")
    
    text = transcript   # STT 결과 (str 타입)
    # print(text)


    ### LLM 답변 반환
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "너는 사용자 문장의 감정을 분석하고, 감정에 맞는 이모티콘만 반환하는 AI다. 사용자의 문장을 읽고 감정을 분석한 뒤, 그 감정을 가장 잘 표현하는 이모티콘을 '하나만' 반환할 것. 절대 문장이나 설명을 반환하지 말고 오직 이모티콘 하나만 반환해야 함. 또한 여러 감정이 섞이면, 가장 지배적인 감정에 맞는 이모티콘만 반환."},  # 시스템 프롬프트
                {"role": "user", "content": text}    # 사용자 텍스트
            ],
            temperature=1,
            max_completion_tokens=5,   # 답변의 최대 글자 토큰 수(이모티콘 하나에 보통 1~4토큰)
            # top_p는 생성 다양성,
            # stream=True는 응답 스트리밍,
            # stop은 생성 중단 조건을 설정.
        )
    
    except Exception as e :
        raise HTTPException(status_code=500, detail=f"LLM Error : {e}")

    answer = completion.choices[0].message.content.strip()  # 답변 문자열의 공백, 줄바꿈 제거
    


    return answer