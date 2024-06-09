#타임아웃 오류 제거

import time
import random
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import discord
from discord.ext import commands, tasks
import asyncio
from mydiscord import YOUR_DISCORD_CHANNEL_ID, YOUR_USER_ID, DISCORD_BOT_TOKEN
from datetime import datetime, timedelta
from collections import defaultdict
import concurrent.futures
import pickle
import re
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

ALLOWED_USER_IDS = [YOUR_USER_ID]  # 허용할 사용자 ID를 추가합니다.
ALLOWED_CHANNEL_IDS = [YOUR_DISCORD_CHANNEL_ID]  # 허용할 서버 ID를 추가합니다.

# 갱신 주기 설정
UPDATE_INTERVAL = 3  # 분 단위로 갱신 주기를 설정합니다.

# 크롤링할 방탈출 카페의 URL 리스트
urls = [
    ('레다스퀘어', 'https://ledasquare.com/layout/res/home.php?go=rev.make', ['레다'], '세상의 진실을 마주하는 일에 대하여'),
    ('골든타임이스케이프2호점', 'https://xn--bb0b44mb8pfwi.kr/layout/res/home.php?go=rev.make&s_zizum=2', ['골든타임2', '골타2'], '그날의 함성 (드라마)'),
    ('룸즈에이부평점', 'http://roomsa.co.kr/sub/sub04.asp?R_JIJEM=S21', ['룸에부평'], '아이언 게이트 프리즌', '놈즈 : 더 비기닝')
]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

my_direct = None  # on_ready에서 넣음. 이땐 서버에 연결 안돼서 미리 못함.

current_data_donetime = None
current_data = {}
data_initialized = False
data_reboot = False
change_log = []
current_data_history = []  # 갱신된 모든 내용을 저장할 리스트

update_lock = asyncio.Lock()  # 업데이트 락 추가

@bot.event
async def on_message(message):
    if message.author.bot:  # 다른 봇의 메시지는 무시합니다.
        return

    if isinstance(message.channel, discord.DMChannel):
        if message.author.id not in ALLOWED_USER_IDS:
            return  # 허용되지 않은 사용자가 DM을 보낸 경우 무시합니다.
    else:
        if message.channel.id not in ALLOWED_CHANNEL_IDS:
            return  # 허용되지 않은 채널에서 온 메시지는 무시합니다.

    await bot.process_commands(message)  # 다른 명령어를 계속 처리합니다.

def save_data(filename, data):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)

def load_data(filename):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def extract_last_update_time(history):
    if not history:
        return None
    last_entry = history[-1]
    last_update_time_str = re.search(r'갱신 시간: ([\d-]+\s[\d:]+)', last_entry).group(1)
    last_update_time = datetime.strptime(last_update_time_str, '%Y-%m-%d %H:%M:%S')
    return last_update_time

def get_korean_weekday_name(date_obj):
    weekdays_korean = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    return weekdays_korean[date_obj.weekday()]


def sync_crawl_ledasquare(url):
    print(f"크롤링 시작: 레다스퀘어 ({url})")
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--headless')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)

    success = False

    while not success:
        try:
            driver.get(url)
            WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.day_index')))
            print("레다스퀘어 페이지 로드 완료")
            my_direct.send("레다스퀘어 페이지 로드 완료")
            success = True
        except TimeoutException:
            print("레다스퀘어 페이지 로드 타임아웃. 재시도 중...")
            my_direct.send("레다스퀘어 페이지 로드 타임아웃. 재시도 중...")
            time.sleep(5)  # 잠시 대기 후 재시도

    def extract_available_dates(driver):
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        dates = soup.find_all('a', class_='day_index')
        available_dates = [(date.get('href').split("'")[1], date.get('href').split("'")[3]) for date in dates if
                           'none' not in date.get('class', [])]
        return available_dates

    available_dates = extract_available_dates(driver)
    #print(f"레다스퀘어 - 예약 가능한 날짜 (현재 달): {available_dates}")
    print(f"레다스퀘어 - 예약 가능한 날짜 (현재 달) 완료")

    try:
        next_button = driver.find_element(By.CSS_SELECTOR, 'a.cal_arr.next')
        if next_button:
            next_button.click()
            time.sleep(2)
            available_dates.extend(extract_available_dates(driver))
            #print(f"레다스퀘어 - 예약 가능한 날짜 (다음 달): {available_dates}")
            print(f"레다스퀘어 - 예약 가능한 날짜 (다음 달) 완료")
    except Exception as e:
        print(f"레다스퀘어 - 다음 달 버튼 클릭 실패: {e}")

    available_times = []
    for date, day_id in available_dates:
        date_click_script = f"javascript:fun_days_select('{date}', '{day_id}')"
        driver.execute_script(date_click_script)
        time.sleep(1)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        times = soup.find_all('a', href=lambda href: href and href.startswith("javascript:fun_theme_time_select"))
        for time_tag in times:
            span_tag = time_tag.find('span')
            if span_tag:
                time_text = span_tag.get_text(strip=True)
                available_times.append((date, time_text))

    driver.quit()
    #print(f"레다스퀘어 - 예약 가능한 시간: {available_times}")
    print(f"레다스퀘어 - 예약 가능한 시간 완료")
    return [("세상의 진실을 마주하는 일에 대하여", date, time_text) for date, time_text in available_times]

def sync_crawl_goldentimeescape(url):
    print(f"크롤링 시작: 골든타임이스케이프2호점 ({url})")
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--headless')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)

    success = False

    while not success:
        try:
            driver.get(url)
            WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, "//input[@name='rev_days']")))
            print("페이지 로드 완료")
            my_direct.send("골타2 페이지 로드 완료")
            success = True
        except TimeoutException:
            print("페이지 로드 타임아웃. 재시도 중...")
            my_direct.send("골타2 페이지 로드 타임아웃. 재시도 중...")
            time.sleep(5)  # 잠시 대기 후 재시도

    available_dates = []
    available_times = []

    def extract_available_dates(calendar_loaded=False):
        if not calendar_loaded:
            driver.execute_script("javascript:fun_calendar('register.rev_days','B','img_001');")
            time.sleep(1)
            driver.switch_to.frame("pop_frame_cal")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        dates = soup.find_all('a', href=lambda href: href and "javascript:fun_put_date" in href)
        available_dates = [date.get('href').split("'")[3] for date in dates if
                           not date.find_parent('li') or date.find_parent('li').get('class') != ['today']]
        #print(f"골든타임이스케이프2호점 - 예약 가능한 날짜: {available_dates}")
        print(f"골든타임이스케이프2호점 - 예약 가능한 날짜 완료")
        driver.switch_to.default_content()
        return available_dates

    def extract_times_for_dates(date):
        nonlocal available_times
        try:
            driver.execute_script("javascript:fun_calendar('register.rev_days','B','img_001');")
            time.sleep(1)
            driver.switch_to.frame("pop_frame_cal")

            date_click_script = f"javascript:fun_put_date('register.rev_days','{date}')"
            driver.execute_script(date_click_script)
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            theme_div = soup.find('div', class_='theme_box')
            if theme_div:
                theme_title = theme_div.find('h3', class_='h3_theme')
                if theme_title and '그날의 함성  (드라마)' in theme_title.get_text(strip=True):
                    times = theme_div.find_all('a', href=lambda href: href and "home.php?go=rev.make.input" in href)
                    for time_tag in times:
                        time_text = time_tag.find('span', class_='time').get_text(strip=True)
                        available_times.append(("그날의 함성 (드라마)", date, time_text))
            driver.switch_to.default_content()
        except Exception as e:
            print(f"골든타임이스케이프2호점 - 시간 추출 실패 ({date}): {e}")

    dates = extract_available_dates()
    for date in dates:
        extract_times_for_dates(date)

    try:
        driver.execute_script("javascript:fun_calendar('register.rev_days','B','img_001');")
        time.sleep(1)
        driver.switch_to.frame("pop_frame_cal")

        next_button = driver.find_element(By.XPATH, "//li[@class='next']/font/a")
        if next_button:
            next_button.click()
            time.sleep(2)
            dates = extract_available_dates(calendar_loaded=True)
            for date in dates:
                extract_times_for_dates(date)
    except Exception as e:
        print(f"골든타임이스케이프2호점 - 다음 달 버튼 클릭 실패: {e}")

    driver.quit()
    #print(f"골든타임이스케이프2호점 - 예약 가능한 시간: {available_times}")
    print(f"골든타임이스케이프2호점 - 예약 가능한 시간 완료")
    return available_times

def sync_crawl_roomsa(url):
    print(f"크롤링 시작: 룸즈에이부평점 ({url})")
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--headless')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)  # 페이지 로드 타임아웃 설정 (초 단위)

    success = False

    while not success:
        try:
            driver.get(url)
            WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href^="?chois_date="]')))
            print("페이지 로드 완료")
            my_direct.send("룸에부평 페이지 로드 완료")
            success = True
        except TimeoutException:
            print("페이지 로드 타임아웃. 재시도 중...")
            my_direct.send("룸에부평 페이지 로드 타임아웃. 재시도 중...")
            time.sleep(5)  # 잠시 대기 후 재시도

    available_dates = []
    available_times = []

    def extract_available_dates():
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        dates = soup.find_all('a', href=lambda href: href and href.startswith("?chois_date="))
        available_dates = [date.get('href').split("&")[0].split("=")[1] for date in dates]
        #print(f"룸즈에이부평점 - 예약 가능한 날짜: {available_dates}")
        print(f"룸즈에이부평점 - 예약 가능한 날짜 완료")
        return available_dates

    def extract_times_for_dates(date, theme_id, theme_name):
        nonlocal available_times
        try:
            date_click_script = f"javascript:location.href='sub04.asp?chois_date={date}&R_JIJEM=S21'"
            driver.execute_script(date_click_script)
            time.sleep(2)

            theme_click_script = f"javascript:location.href='sub04.asp?R_JIJEM=S21&chois_date={date}&R_THEMA={theme_id}&DIS_T=#time'"
            driver.execute_script(theme_click_script)
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            times = soup.find_all('a', href=lambda href: href and f"chois_date={date}&room_time=" in href and f"R_THEMA={theme_id}" in href)
            for time_tag in times:
                time_text = time_tag.find('li').get_text(strip=True)
                available_times.append((theme_name, date, time_text))
        except Exception as e:
            print(f"룸즈에이부평점 - 시간 추출 실패 ({date}, {theme_name}): {e}")

    def fetch_dates_and_times():
        dates = extract_available_dates()
        for date in dates:
            extract_times_for_dates(date, "Roomsa_R67", "아이언 게이트 프리즌")
            extract_times_for_dates(date, "Roomsa_R68", "놈즈 : 더 비기닝")

    def find_next_month_button(driver):
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        next_month_links = soup.find_all('a', href=lambda href: href and "?R_JIJEM=S21&y=" in href)

        print(f"다음 달 링크 후보: {[link.get('href') for link in next_month_links]}")

        if len(next_month_links) != 2:
            return None

        link1, link2 = next_month_links
        print(f"링크 1: {link1.get('href')}")
        print(f"링크 2: {link2.get('href')}")

        year1, month1 = map(int, [param.split('=')[1] for param in link1.get('href').split('&') if
                                  param.startswith(('y=', 'm='))])
        year2, month2 = map(int, [param.split('=')[1] for param in link2.get('href').split('&') if
                                  param.startswith(('y=', 'm='))])

        print(f"링크 1 - 연도: {year1}, 월: {month1}")
        print(f"링크 2 - 연도: {year2}, 월: {month2}")

        if (year1 > year2) or (year1 == year2 and month1 > month2):
            print(f"선택된 링크: {link1.get('href')}")
            return link1
        else:
            print(f"선택된 링크: {link2.get('href')}")
            return link2

    fetch_dates_and_times()

    try:
        next_button = find_next_month_button(driver)
        if next_button:
            next_button_href = next_button.get("href")
            next_button = driver.find_element(By.XPATH, f"//a[@href='{next_button_href}']")
            driver.execute_script("arguments[0].click();", next_button)
            time.sleep(2)
            fetch_dates_and_times()
    except Exception as e:
        print(f"룸즈에이부평점 - 다음 달 버튼 클릭 실패: {e}")

    driver.quit()
    #print(f"룸즈에이부평점 - 예약 가능한 시간: {available_times}")
    print(f"룸즈에이부평점 - 예약 가능한 시간 완료")
    return available_times

async def fetch_all_data():
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        ledasquare_future = loop.run_in_executor(executor, sync_crawl_ledasquare, urls[0][1])
        goldentimeescape_future = loop.run_in_executor(executor, sync_crawl_goldentimeescape, urls[1][1])
        roomsa_future = loop.run_in_executor(executor, sync_crawl_roomsa, urls[2][1])

        results = await asyncio.gather(ledasquare_future, goldentimeescape_future, roomsa_future)

    all_themes = []
    for cafe_info, themes in zip(urls, results):
        cafe_name = cafe_info[0]
        for theme in themes:
            all_themes.append((cafe_name, theme[0], theme[1], theme[2]))

    grouped_themes = {}
    for cafe, t_name, date, t_time in all_themes:
        key = (cafe, t_name)
        if key not in grouped_themes:
            grouped_themes[key] = {}
        if date not in grouped_themes[key]:
            grouped_themes[key][date] = []
        grouped_themes[key][date].append(t_time)

    for cafe_info in urls:
        cafe_name = cafe_info[0]
        for t_name in [theme[1] for theme in all_themes if theme[0] == cafe_name]:
            if (cafe_name, t_name) not in grouped_themes:
                grouped_themes[(cafe_name, t_name)] = {}

    #print(f"데이터 수집 완료: {grouped_themes}")

    '''
    data_str = str(grouped_themes)
    if len(data_str) > 2000:
        chunks = [data_str[i:i+2000] for i in range(0, len(data_str), 2000)]
        for chunk in chunks:
            await my_direct.send(chunk)
    else:
        await my_direct.send(data_str)
    '''

    print("데이터 수집 완료")
    #await my_direct.send("데이터 수집 완료")

    return grouped_themes

def compare_data(old_data, new_data):
    added_times = []
    removed_times = []

    for key, new_dates in new_data.items():
        old_dates = old_data.get(key, {})
        for date, new_times in new_dates.items():
            old_times = old_dates.get(date, [])
            added = [time for time in new_times if time not in old_times]
            removed = [time for time in old_times if time not in new_times]
            if added:
                added_times.append((key, date, added))
            if removed:
                removed_times.append((key, date, removed))
    return added_times, removed_times

@tasks.loop(minutes=UPDATE_INTERVAL)
async def check_updates():
    global current_data, current_data_donetime, data_initialized, change_log, current_data_history,data_reboot
    channel = bot.get_channel(YOUR_DISCORD_CHANNEL_ID)

    if channel is None:
        print("채널 ID가 유효하지 않습니다. 봇이 채널에 접근할 수 있는지 확인하세요.")
        await my_direct.send("채널 ID가 유효하지 않습니다. 봇이 채널에 접근할 수 있는지 확인하세요.")
        return

    if not update_lock.locked():
        async with update_lock:

            try:
                if not data_initialized:
                    await my_direct.send("목록을 초기화합니다.")
                    current_data = await fetch_all_data()
                    now = datetime.now() + timedelta(hours=9)
                    current_data_donetime = now.strftime('%Y-%m-%d %H:%M:%S')  # 갱신 완료 시간을 저장
                    current_data_history.append(f"현재 가능한 테마 목록 (갱신 시간: {current_data_donetime}):\n{current_data}")
                    #save_data('current_data.pkl', current_data)
                    save_data('change_log.pkl', change_log)
                    save_data('current_data_history.pkl', current_data_history)
                    data_initialized = True
                    await my_direct.send("갱신 완료 : 첫 갱신입니다.")
                    return

                await my_direct.send("목록을 갱신합니다.")
                new_data = await fetch_all_data()

                added_times, removed_times = compare_data(current_data, new_data)
                current_data = new_data
                now = datetime.now() + timedelta(hours=9)
                current_data_donetime = now.strftime('%Y-%m-%d %H:%M:%S')  # 갱신 완료 시간을 저장
                current_data_history.append(f"갱신 완료\n현재 가능한 테마 목록 (갱신 시간: {current_data_donetime}):\n{current_data}")
                #save_data('current_data.pkl', current_data)
                save_data('current_data_history.pkl', current_data_history)
                data_reboot2 = data_reboot

                if not added_times and not removed_times:
                    await my_direct.send("갱신 완료 : 변동 사항이 없습니다.")
                elif data_reboot2 :
                    await my_direct.send("갱신 완료 : 서버 재가동 후 첫 갱신입니다.")
                    data_reboot = False
                else:
                    await my_direct.send("갱신 완료 : 변동 사항이 있습니다.")
                    now = datetime.now() + timedelta(hours=9)
                    if added_times:
                        for (cafe, t_name), date, times in added_times:
                            message = f"{now.strftime('%Y-%m-%d %H:%M:%S')}\n새로운 가능한 시간\n{cafe}: {t_name} - {date} {', '.join(times)}"
                            change_log.append((now, message))
                            save_data('change_log.pkl', change_log)
                            await channel.send(message)

                    if removed_times:
                        for (cafe, t_name), date, times in removed_times:
                            message = f"{now.strftime('%Y-%m-%d %H:%M:%S')}\n제거된 시간\n{cafe}: {t_name} - {date} {', '.join(times)}"
                            change_log.append((now, message))
                            save_data('change_log.pkl', change_log)
                            await channel.send(message)
            except Exception as e:  # 추가된 부분
                print(f"갱신 중 오류 발생: {e}")
                await my_direct.send(f"갱신 중 오류 발생: {e}")

    else:
        await my_direct.send("기존 갱신 작업 중 새로운 갱신 작업이 접근하여 차단되었습니다.")

@bot.event
async def on_ready():
    global my_direct, current_data, change_log, current_data_history, data_initialized, data_reboot
    print(f'Logged in as {bot.user}')
    my_direct = await bot.fetch_user(YOUR_USER_ID)
    await my_direct.send(f'Logged in as {bot.user}')
    channel_on_ready = bot.get_channel(YOUR_DISCORD_CHANNEL_ID)

    data_reboot = True

    # 데이터 로드
    #current_data = load_data('current_data.pkl') or {}
    change_log = load_data('change_log.pkl') or []
    current_data_history = load_data('current_data_history.pkl') or []

    # 서버 점검 시간 계산 및 기록
    last_update_time = extract_last_update_time(current_data_history)
    now = datetime.now() + timedelta(hours=9)

    if last_update_time:
        down_time = now - last_update_time
        '''
        down_time_message = (
            f"서버 점검 시간: {last_update_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {now.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(총 {down_time})"
        )
        '''
        down_time_message = (
            f"서버 점검 시간: {last_update_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {now.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        change_log.append((now.strftime('%Y-%m-%d %H:%M:%S'),
                           down_time_message))
        save_data('change_log.pkl', change_log)
        await channel_on_ready.send(down_time_message)
        await my_direct.send(down_time_message)
        data_initialized = True  # current_data_history 가 존재할 시 초기화 생략


    await channel_on_ready.send(f"서버 가동을 시작합니다. ({UPDATE_INTERVAL}분 간격 갱신)")
    check_updates.start()

@bot.command(name='목록')
async def list_themes(ctx, cafe_name: str = None):
    try:
        await my_direct.send("!목록 명령어가 실행되었습니다.")
        if current_data == {}:
            await ctx.send(f"서버 가동 후 {UPDATE_INTERVAL}분간 기다려주세요.")
            return

        response_text = f"현재 가능한 테마 목록 (갱신 시간: {current_data_donetime}):\n\n"
        for (cafe, t_name), dates in current_data.items():
            # 카페 이름 또는 줄임말로 조회
            cafe_info = next((info for info in urls if cafe in info or cafe in info[2]), None)
            if cafe_name and (cafe_name != cafe and cafe_name not in (cafe_info[2] if cafe_info else [])):
                continue
            response_text += f"{cafe}: {t_name}\n"
            if dates:
                for date, times in dates.items():
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    #formatted_date = date_obj.strftime('%m월 %d일 ') + get_korean_weekday_name(date_obj)
                    formatted_date = f"{date_obj.month}/{date_obj.day}({date_obj.strftime('%a')})".replace('Mon',
                                                                                                           '월').replace(
                        'Tue', '화').replace('Wed', '수').replace('Thu', '목').replace('Fri', '금').replace('Sat',
                                                                                                        '토').replace(
                        'Sun', '일')
                    response_text += f"{formatted_date} {' '.join(times)}\n"
            else:
                response_text += " - X\n"
            response_text += "\n"

        await ctx.send(response_text)
    except Exception as e:
        await ctx.send("목록 요청을 처리하는 중 오류가 발생했습니다.")
        print("목록 요청을 처리하는 중 오류가 발생했습니다.:", str(e))
        await my_direct.send("목록 요청을 처리하는 중 오류가 발생했습니다.:" + str(e))

'''
@bot.command(name='확인')
async def check_availability(ctx, cafe_name: str):
    try:
        await my_direct.send("!확인 명령어가 실행되었습니다.")
        loop = asyncio.get_running_loop()

        # 카페 이름 또는 줄임명으로 조회
        cafe_info = next((cafe for cafe in urls if cafe_name == cafe[0] or cafe_name in cafe[2]), None)

        if not cafe_info:
            await ctx.send("유효한 카페 이름을 입력해 주세요.")
            return

        # list_themes 함수를 사용하여 특정 카페 정보만 출력
        await list_themes(ctx, cafe_name=cafe_info[0])

    except Exception as e:
        await ctx.send("확인 요청을 처리하는 중 오류가 발생했습니다.")
        print("확인 요청을 처리하는 중 오류가 발생했습니다.:", str(e))
        await my_direct.send("확인 요청을 처리하는 중 오류가 발생했습니다.:" + str(e))
'''

@bot.command(name='기록')
async def check_logs(ctx):
    await my_direct.send("!기록 명령어가 실행되었습니다.")
    now = datetime.now() + timedelta(hours=9)
    cutoff_time = now - timedelta(days=7)

    #recent_changes = [log for log in change_log if log[0] > cutoff_time]
    recent_changes = []
    for log_time, log_message in change_log:
        try:
            log_time_obj = log_time if isinstance(log_time, datetime) else datetime.strptime(log_time, '%Y-%m-%d %H:%M:%S')
            if log_time_obj > cutoff_time:
                recent_changes.append((log_time_obj, log_message))
        except ValueError:
            continue

    if recent_changes:
        grouped_changes = defaultdict(list)
        for log_time, log_message in recent_changes:
            grouped_changes[log_time].append(log_message)

        response_text = "최근 일주일 기록\n"
        for log_time, messages in sorted(grouped_changes.items()):
            new_available_text = "- 새로운 가능한 시간\n"
            removed_text = "- 제거된 시간\n"
            downtime_text = "- 서버 점검\n"

            new_available_log = ""
            removed_log = ""
            downtime_log = ""

            for log_message in messages:
                if "새로운 가능한 시간" in log_message:
                    message_parts = log_message.split('\n', 2)
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}', message_parts[2])
                    if date_match:
                        date_str = date_match.group()
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        formatted_date = f"{date_obj.month}/{date_obj.day}({date_obj.strftime('%a')})".replace('Mon', '월').replace('Tue', '화').replace('Wed', '수').replace('Thu', '목').replace('Fri', '금').replace('Sat', '토').replace('Sun', '일')
                        message_parts[2] = message_parts[2].replace(date_str, formatted_date)
                    new_available_log += message_parts[2] + "\n"
                elif "제거된 시간" in log_message:
                    message_parts = log_message.split('\n', 2)
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}', message_parts[2])
                    if date_match:
                        date_str = date_match.group()
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        formatted_date = f"{date_obj.month}/{date_obj.day}({date_obj.strftime('%a')})".replace('Mon', '월').replace('Tue', '화').replace('Wed', '수').replace('Thu', '목').replace('Fri', '금').replace('Sat', '토').replace('Sun', '일')
                        message_parts[2] = message_parts[2].replace(date_str, formatted_date)
                    removed_log += message_parts[2] + "\n"
                elif "서버 점검" in log_message:
                    downtime_log += "[" + log_message.split(": ", 1)[1] + "]" + "\n"

            if downtime_log == "":
                response_text += f"[{log_time.strftime('%Y-%m-%d %H:%M:%S')}]\n"

            if new_available_log != "":
                response_text += new_available_text + new_available_log
                if removed_log == "":
                    response_text += "\n"
            if removed_log != "":
                response_text += removed_text + removed_log + "\n"
            if downtime_log != "":
                response_text += downtime_log + downtime_text + "\n"

        response_text_chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
        for chunk in response_text_chunks:
            await ctx.send(chunk)
    else:
        await ctx.send("최근 일주일 내 변동사항이 없습니다.")


@bot.command(name='카페')
async def list_cafes(ctx):
    try:
        await my_direct.send("!카페 명령어가 실행되었습니다.")
        response_text = "검색 대상 카페와 테마 목록:\n"
        for cafe_info in urls:
            cafe_name = cafe_info[0]
            abbreviations = ", ".join(cafe_info[2])
            themes = ", ".join(cafe_info[3:])
            response_text += f"{cafe_name} ({abbreviations}): {themes}\n"

        await ctx.send(response_text)
    except Exception as e:
        await ctx.send("카페 목록 요청을 처리하는 중 오류가 발생했습니다.")
        print("카페 목록 요청을 처리하는 중 오류가 발생했습니다.:", str(e))
        await my_direct.send("카페 목록 요청을 처리하는 중 오류가 발생했습니다.:" + str(e))


@bot.command(name='명령어')
async def list_commands(ctx):
    try:
        await my_direct.send("!명령어 명령어가 실행되었습니다.")
        response_text = "사용 가능한 명령어 목록:\n"
        response_text += "!목록 [카페 이름 (선택사항)] - 현재 가능한 테마 목록을 표시합니다.\n"
        #response_text += "!확인 [카페 이름 (줄임말)] - 특정 카페의 예약 가능 시간을 확인합니다.\n"
        response_text += "!기록 - 최근 일주일 기록을 표시합니다.\n"
        response_text += "!카페 - 검색 대상 카페와 테마 목록을 표시합니다.\n"

        await ctx.send(response_text)
    except Exception as e:
        await ctx.send("명령어 목록 요청을 처리하는 중 오류가 발생했습니다.")
        print("명령어 목록 요청을 처리하는 중 오류가 발생했습니다.:", str(e))
        await my_direct.send("명령어 목록 요청을 처리하는 중 오류가 발생했습니다.:" + str(e))

TOKEN = DISCORD_BOT_TOKEN

bot.run(TOKEN)