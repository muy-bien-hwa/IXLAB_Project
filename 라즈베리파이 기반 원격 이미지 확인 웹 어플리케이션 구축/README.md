pc ip 바뀔 시 live_camera.py 내 SERVER_URL 수정해야 함.
rasp ip 바뀔 시 Stream.jsx 내 PI_SERVER 수정해야 함.

live_camera.py와 pi_fapi가 같이 묶여있으니, pi_fapi 실행 시 uvicorn --reload 옵션 추가 금지.



라즈베리파이 디렉토리 구성

home/(user_name) …

project
	- log.log
	↓ video
		↓ ringbf ( 링버퍼 저장 )
			ringbf_{timestamp}.h264
		↓ event  ( 업로드 영상 merge용 )
			event_{timestamp}.h264
		↓ upload ( 업로드용 )
			event_{timestamp}.mp4
			concat_{timestamp}.txt  ( 영상 merge 후 삭제 )


서버 백엔드 디렉토리 구성

main.py
    ↓ controller
        __init__.py
        eventlist.py
        piUpload.py
    ↓ uploaded
        파이로부터 업로드 된 영상들(.mp4) 저장

