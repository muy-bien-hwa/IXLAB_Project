# 라즈베리파이 -> 서버 업로드 라즈베리파이용


import subprocess  # 파이썬에서 외부 프로그 실행할 수 있게 해주는 라이브러
import requests  # HTTP POST 요청 보내기 위한 라이브러리
from datetime import datetime  # 날짜 시간
import os  # 파일/폴더 생성, 삭제, 경로 처리 등...
import signal  # 프로그램 종료(컨트롤+C, 종료 명령) 감지하는 모듈
import logging  # 로그 남기는 라이브러리. print로 남겨도 되지만 더 전문적인? 로그 방식
import threading   # 업로드 병렬 처리 위해
import time   # Hold Timer 로직 위해
import cv2   # 모션 인식
import numpy   # 영상 바이트 정보를 numpy array로 변환
from collections import deque   # 링버퍼 구현을 위해서
import websocket



# 업로드 서버 주소
SERVER_URL = "http://192.168.0.4:8000/piupload/"
# 라즈베리파이 내 영상 저장 주소
VIDEO_DIR = "/home/ybh3008/project/video"  # 실시간 감시 영상 세그먼트는 segment에, 이벤트 영상은 event에 저장
# 업로드 실패 시 최대 재시도 횟수
MAX_RETRIES = 3
# 재시도 사이에 기다리는 시간(초)
RETRY_DELAY = 5
# Hold Timer 로직 중 얼마나 Hold 할건지(초)
EVENT_HOLD_SEC = 3.0


# 영상 설정
WIDTH = 640
HEIGHT = 360   # 360p
FPS = 30   # 30 프레임
FRAME_SIZE = (WIDTH * HEIGHT * 3) // 2   # YUV420으로 받을 때 필요. 정수로 입력해야 하기 때문에 // 이용
CHECK_FRAME_TERM = 10   # 몇 프레임 당 한 번씩 검사할건지
RINGBF_MAX_TIME = 3   # 최대 몇 초 프레임메모리에 저장할건지


ringbf = deque(maxlen = FPS*RINGBF_MAX_TIME)   # 링버퍼 생성
MOTION_THRESHOLD = 25   # 픽셀 차이 임계값 (1~255)
THRESHOLD_PIXEL_COUNT = (WIDTH * HEIGHT) * 0.05   # 임계값 넘은 픽셀이 얼마나 되어야 이벤트로 판정지을 것이냐. [ 전체 픽셀 중 5% ]










### 로그 형식 logging_config
logging.basicConfig(
    level = logging.INFO,  # INFO 이상 등급의 로그만 출력 (debug < info < warning < error < critical)
    format = "%(asctime)s [%(levelname)s] %(message)s",  # log 출력 포맷 설정
    handlers = [   # 로그 메시지 출력 방법 설정
        logging.StreamHandler(),   # 스트림 터미널에 출력
        logging.FileHandler("/home/ybh3008/project/log1.log")   # 파일(log.log)로 저장
    ]
)


logger = logging.getLogger(__name__)  # 로그 객체 생성. 이름은 __name__(현재 파일 이름)
   
   






running = True


### 종료 시그널 인식 코드
def exit_signal(signum, frame):
    global running
    logger.info("종료 시그널 수신")
    running = False
    if event_proc:  # 이벤트 녹화 중이면 종료
        event_proc.terminate()
        event_proc.wait()


signal.signal(signal.SIGINT, exit_signal)   # 컨트롤 C 종료 인식
signal.signal(signal.SIGTERM, exit_signal)   # kill, systemd 종료 인식










stream_proc = None   # 스트림 녹화 프로세스


### 카메라 작동하는 코드
def start_camera():
    global stream_proc
    logger.info("스트림 시작")
    stream_proc = subprocess.Popen(
    [
        "rpicam-vid",
        "-t", "0",
        "--width", str(WIDTH),
        "--height", str(HEIGHT),
        "--framerate", str(FPS),
        "--codec", "yuv420",   # YUV420으로 받음. 프레임 단위로 분석할 수 있도록
        "--nopreview",
        "-o", "-"          # stdout으로 출력
    ],
        stdout = subprocess.PIPE,   # rpicam-vid로 촬영한 영상 바이트를 파이프로 받겠다.
        bufsize = FRAME_SIZE   # 버퍼 사이즈 = YUV420의 한 프레임 사이즈. 한 프레임씩 받겠다.
    )
   






# start_camera 로부터 frame 읽어보는 코드
def read_frame():
    return stream_proc.stdout.read(FRAME_SIZE)
   








event_proc = None   # 이벤트 프로세스
timestamp = None   # 이벤트 발생 시간
event_filepath = ""   # 이벤트 파일 경로
   
### 이벤트 프레임 실시간 ffmpeg 코드
def start_event_frame(frame_byte):
    global event_proc, timestamp, event_filepath
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  #년월일_시분초 형식으로
        logger.info(f"이벤트 영상 시작 : {timestamp}")
        event_filepath = os.path.join(VIDEO_DIR, "event", f"event_{timestamp}.h264")
   
        event_proc = subprocess.Popen([
            "ffmpeg",
            "-f", "rawvideo",
            "-pix_fmt", "yuv420p",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-r", str(FPS),
            "-i", "-",  # stdin으로 받음
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-y",
            event_filepath
        ],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        event_proc.stdin.write(frame_byte)
       
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.error(f"이벤트 프레임 저장 실패 : {e}")
       
 
 
       
       
### 이벤트 프레임에 프레임 집어넣는 코드
def event_frame(frame_byte):
    if event_proc and event_proc.stdin:
        event_proc.stdin.write(frame_byte)








### 이벤트 프레임 마감치는 코드
def end_event_frame(frame_byte):
    global event_proc
    if event_proc and event_proc.stdin:
        event_proc.stdin.write(frame_byte)
    
    event_proc.stdin.close()
    try:
        event_proc.wait(timeout=3)   # 녹화 프로세스가 종료되길 기다림. 종료 안되면 timeouterror
        if event_proc.returncode != 0:
            stderr = event_proc.stderr.read().decode()
            logger.error(f"event ffmpeg 인코딩 실패 : {stderr}")
            raise RuntimeError("event ffmpeg 인코딩 실패")
       
    except subprocess.TimeoutExpired:
        logger.error("이벤트 녹화 종료 timeout, 강제 종료")
        event_proc.kill()
        event_proc.wait()
       
        event_proc = None
       
    # 파일 잘 만들어졌는지 확인
    if not os.path.exists(event_filepath):
        logger.error(f"영상 녹화 실패 : file not created at {event_filepath}")
        raise RuntimeError("영상 녹화 실패 : file not created")


    # 파일 크기가 0이 아닌지 확인.
    size = os.path.getsize(event_filepath)  # bite 단위
    if size == 0:
        os.remove(event_filepath)
        logger.error(f"영상 녹화 실패 : file size is 0 at {event_filepath}")
        raise RuntimeError("영상 녹화 실패 : file size is 0")






ringbf_h264_filepath = ""


### ringbf -> h264 인코딩
def ringbf_to_h264(ringbf):
    global ringbf_h264_filepath
    ringbf_h264_filepath = os.path.join(VIDEO_DIR, "ringbf", f"ringbf_{timestamp}.h264")
   
    try:
        proc = subprocess.Popen([
            "ffmpeg",
            "-f", "rawvideo",
            "-pix_fmt", "yuv420p",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-r", str(FPS),
            "-i", "-",   # stdin으로 입력받음
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-y",  # 덮어쓰기
            ringbf_h264_filepath
        ],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
       
        for frame in ringbf:
            proc.stdin.write(frame)
       
        proc.stdin.close()
        proc.wait()
       
        if proc.returncode != 0:   # returncode가 0이면 ffmpeg 정상 작동했다는 뜻
            logger.error("링버퍼 ffmpeg 인코딩 실패")
            raise RuntimeError("링버퍼 ffmpeg 인코딩 실패")


        logger.info(f"링버퍼 인코딩 완료 : {ringbf_h264_filepath}")
        return ringbf_h264_filepath
   
   
    except Exception as e:
        logger.error(f"링버퍼 인코딩 중 오류 : {e}")
        raise RuntimeError(f"링버퍼 인코딩 중 오류")
   
   
   
   




# 업로드용 파일(mp4) 만들기 (링버퍼 + 이벤트 merge, convert)
def merge_ringbf_event(ringbf_h264_filepath, event_filepath):
    global final_mp4_filepath
    final_mp4_filepath = os.path.join(VIDEO_DIR, "upload", f"event_{timestamp}.mp4")   # 최종 업로드 파일 경로
    concat_list_path = os.path.join(VIDEO_DIR, "upload", f"concat_{timestamp}.txt")
   
    try:
        with open(concat_list_path, "w") as f:
            f.write(f"file '{ringbf_h264_filepath}'\n")   # 링버퍼 h264 변환 파일 주소
            f.write(f"file '{event_filepath}'\n")   # 이벤트 영상 h264 파일 주소
       
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                final_mp4_filepath
            ],
            check = True
        )
   
        if not os.path.exists(final_mp4_filepath):
            logger.error(f"mp4 파일 생성 실패 : 파일이 존재하지 않음. {final_mp4_filepath}")
            raise RuntimeError("mp4 파일 생성 실패 : 파일이 존재하지 않음.")


        if os.path.getsize(final_mp4_filepath) == 0:
            logger.error(f"mp4 파일 생성 실패 : 파일 크기 0. {final_mp4_filepath}")
            raise RuntimeError("mp4 파일 생성 실패 : 파일 크기 0.")
       
        logger.info(f"이벤트 영상 머지 완료 : {final_mp4_filepath}")




    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg 머지 실패 : {e}")
        raise RuntimeError("ffmpeg 머지 실패")
   
    os.remove(concat_list_path)   # 다 쓴 concat_list_path 삭제
   
   
   






### 영상 업로드 코드
def upload_video_thread(upload_filepath):
    for t in range(MAX_RETRIES):
        try:
            logger.info(f"영상 업로드 시도 {t+1}회 : {upload_filepath}")
           
            with open(upload_filepath, "rb") as f:   # 영상 파일은 바이너리 데이터라서 읽기, 바이너리("rb") 모드로 open
                files = {
                    "file": (
                        os.path.basename(upload_filepath),
                        f,
                        "video/mp4"   # mp4 형
                    )
                }
               
                # 서버로 POST 요청
                response = requests.post(
                    SERVER_URL,
                    files=files,
                    timeout=10
                )
               
                if response.status_code == 200:
                    logger.info(f"영상 업로드 성공 : {upload_filepath}")
                    os.remove(ringbf_h264_filepath)
                    os.remove(event_filepath)
                    return True
                else:
                    logger.error(f"파일 업로드 실패 : {response.status_code}")
               
        except Exception as e:
            logger.error(f"파일 업로드 실패 : {e}")
           
        if t < MAX_RETRIES:
            logger.info(f"{RETRY_DELAY}초 후 재시도")
            time.sleep(RETRY_DELAY)
   
    logger.error(f"최대 재시도 초과. 업로드 실패 : {upload_filepath}")
    return False








   
   


### 실시간 픽셀 검사 코드
def check_event(prev_frame_byte, curr_frame_byte):
    global event_detected
   
    # Y plane(밝기 값)만 추출 = grayscale 하는 거랑 비슷
    prev_y = numpy.frombuffer(prev_frame_byte, dtype=numpy.uint8, count=WIDTH*HEIGHT).reshape((HEIGHT, WIDTH))
    curr_y = numpy.frombuffer(curr_frame_byte, dtype=numpy.uint8, count=WIDTH*HEIGHT).reshape((HEIGHT, WIDTH))
   
    # 가우시안 블러로 노이즈 완화
    prev_blur = cv2.GaussianBlur(prev_y, (5, 5), 0)
    curr_blur = cv2.GaussianBlur(curr_y, (5, 5), 0)
   
    # 차이 계산
    diff = cv2.absdiff(prev_blur, curr_blur)
    _, thresh = cv2.threshold(diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)   # 픽셀 간 차이가 MOTION_THRESHOLD 값보다 크면 255로 변환
   
    motion_pixels = cv2.countNonZero(thresh)   # threshold 값을 넘은 픽셀들 카운트
   
    if motion_pixels > THRESHOLD_PIXEL_COUNT:
        return True
    else:
        return False
   
    ################## 밝기 급격하게 변할 때 제외, 외곽일 수록 가중치 더 적게.
   
   






### 멀티스레드
def multi_thread_proc(ringbf):
    try:
        ringbf_to_h264(ringbf)
        merge_ringbf_event(ringbf_h264_filepath, event_filepath)
        upload_video_thread(final_mp4_filepath)
    except Exception as e:
        logger.error(f"이벤트 후처리 실패 : {e}")
   
   
   


### 웹소켓 연결 실시간 스트리밍 코드
ws = None 

def connect_websocket():
    global ws
    try:
        ws = websocket.WebSocket()
        ws.connect("ws://localhost:8000/stream/ws")   # 파이 fapi 웹소켓과 연결
    except Exception as e:
        logger.error(f"WebSocket 연결 실패 : {e}")
        ws = None
    


   
### 메인 코드
def main():
    logger.info("video_uploader_1 프로그램 시작")
    event_detected = False
    switch_on = False
    last_true_time = 0
    frame_count = 0
    prev_frame_byte = None
    curr_frame_byte = None
   
    start_camera()
    connect_websocket()

    while running == True:
        now = time.time()
        frame_byte = read_frame()
        frame_count += 1

        if frame_count % 10 == 0:
            response = requests.get("http://localhost:8000/stream/status")  # 파이 백엔드에서 신호 받기
            streaming_active = response.json()["streaming_active"]
            print(streaming_active)  # 실시간 스트리밍 확인 코드

            curr_frame_byte = frame_byte
            if prev_frame_byte is None:   # 이전 프레임이 없을 때(시작할 때)
                pass
            else:   # 이전 프레임 있음
                event_detected = check_event(prev_frame_byte, curr_frame_byte)
           
            prev_frame_byte = curr_frame_byte
           
            if event_detected:
                last_true_time = now
                if switch_on:   # 이미 한번 스위치가 켜졌다면,
                    event_frame(frame_byte)
                    logger.warning("이벤트 촬영 중. 중복 촬영 방지")
                else:
                    start_event_frame(frame_byte)   # 처음 detected 되었다면 그 프레임부터 계속 event_frame에 집어넣기
                    switch_on = True
           
            else:
                if now - last_true_time >= EVENT_HOLD_SEC and last_true_time != 0 and switch_on:
                    end_event_frame(frame_byte)   # 마지막 event_frame 집어넣기
                    switch_on = False
                    ringbf_copy = list(ringbf)   # 현재 ringbf = deque라서 실시간으로 변함. list로 변환후 저장해서 변하지 않게.
                    threading.Thread(
                        target=multi_thread_proc,
                        args=(ringbf_copy,),
                        daemon=True
                    ).start()
                   
        else:   # 스위치 = 이벤트 촬영 중
            if switch_on:
                event_frame(frame_byte)
            else:
                ringbf.append(frame_byte)


        try:
            if streaming_active and ws:
                frame_byte_copy = bytes(frame_byte)
                yuv_frame = numpy.frombuffer(frame_byte_copy, dtype=numpy.uint8).reshape((int(HEIGHT * 1.5), WIDTH))  # YUV420 형태
                rgb_frame = cv2.cvtColor(yuv_frame, cv2.COLOR_YUV2RGB_I420)  # RGB 변환
                _, jpeg_frame = cv2.imencode('.jpg', rgb_frame)  # JPEG 인코딩
                ws.send(jpeg_frame.tobytes(), opcode=websocket.ABNF.OPCODE_BINARY)  # JPEG 전송
                logger.info("JPEG 프레임 전송")
            else :   # 둘 다 False
                pass
        except Exception as e:
            logger.error(f"WebSocket 프레임 전송 실패: {e}")
            pass
               
               
               
           
if __name__ == "__main__":   # 이 파일 직접 실행할 때 main() 실행
    main()
