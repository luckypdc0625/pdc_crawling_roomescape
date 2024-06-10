안녕하세요.

해당 프로그램은 방탈출카페 홈페이지에서 실시간 예약 현황 정보를 3분마다 크롤링하여 3분 전과 비교하여 변동 사항이 있을 시(예약 취소로 인한 예약 가능 시간 발생, 예약 완료로 인한 예약 가능 시간 소멸) 등록된 디스코드 채널에 디스코드 봇이 자동으로 메세지를 전송하는 프로그램입니다.


<자동 전송 기능 예시>
![auto](https://github.com/luckypdc0625/pdc_crawling_roomescape/assets/38238926/daa6ce3d-cb6c-4d0b-a4af-918d168360ab)


- 그 외 기능
1. !목록 [카페 이름 (선택사항)] - 현재 가능한 모든 테마 목록을 표시합니다.
2. !기록 - 최근 일주일간의 변동 기록을 표시합니다.
3. !카페 - 크롤링 대상 카페와 테마 목록을 표시합니다.


<!기록 명령 예시>
![history](https://github.com/luckypdc0625/pdc_crawling_roomescape/assets/38238926/33c030ea-d032-4a60-96bd-0bc66ec6c8b0)


해당 프로그램은 아래 사이트 3곳에서 크롤링을 진행합니다.

('레다스퀘어', 'https://ledasquare.com/layout/res/home.php?go=rev.make', ['레다'], '세상의 진실을 마주하는 일에 대하여'),
('골든타임이스케이프2호점', 'https://xn--bb0b44mb8pfwi.kr/layout/res/home.php?go=rev.make&s_zizum=2', ['골든타임2', '골타2'], '그날의 함성 (드라마)'),
('룸즈에이부평점', 'http://roomsa.co.kr/sub/sub04.asp?R_JIJEM=S21', ['룸에부평'], '아이언 게이트 프리즌', '놈즈 : 더 비기닝')

mydiscord.py 파일에 실제 정보를 입력하시고 crawling_to_discord.py를 실행해주세요. (mydiscord.py의 YOUR_USER_ID에는 관리하실 분의 디스코드 ID를 넣으셔야 합니다)

'!명령어'를 사용해보세요.

(갱신 주기를 변경하시려면 UPDATE_INTERVAL 변수를 변경하세요.)
