##playwright codegen https://crowdworks.jp/login
from playwright.sync_api import sync_playwright
import time
import re
import google.generativeai as genai
from dotenv import load_dotenv
import os
import csv
import logging
from datetime import datetime
from typing import List, Optional
from linebot.v3.messaging import Configuration, MessagingApi, ApiClient, PushMessageRequest, ApiException
# ファイルの読み込み
# prompts/crowdworks_prompt.pyにあるCROWDWORKS_PROMPTを使う
# .envにprompt/を記載すること
from prompts.crowdworks_prompt import CROWDWORKS_PROMPT

# .envファイルから環境変数を読み込む
# 環境変数の読み込みを確実にする# override=True を追加
load_dotenv(override=True)  
# 環境変数からAPI keyを取得
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
# Gemini APIの設定
genai.configure(api_key=GOOGLE_API_KEY)

CHANNEL_TOKEN = os.getenv('CHANNEL_TOKEN')
USER_ID = os.getenv('USER_ID')
MY_ID = os.getenv('MY_ID')




# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def send_line(linemsg):
    #動くサンプルURLです。
    #見つけるのに苦労した
    #LINE Messaging API SDK for Pythonのv3でpush_messageする
    #公式のREADMEのコードで動かないのは、ワナだと思った。
    #https://mo22comi.com/line-messaging-api-sdk-v3/

    configuration = Configuration(
        access_token = CHANNEL_TOKEN
    )
    message_dict = {
        'to': USER_ID,
        'messages': [
            {'type': 'text', 
             'text': f'{linemsg}'
             }
        ]
    }

    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = MessagingApi(api_client)
        push_message_request = PushMessageRequest.from_dict(message_dict)

        try:
            push_message_result = api_instance.push_message_with_http_info(push_message_request, _return_http_data_only=False)
            print(f'送信メッセージ ： \n{message_dict.get('messages')[0].get('text')}')
            print(f'ライン送信成功 -> status code => {push_message_result.status_code}')

        except ApiException as e:
            print('Exception when calling MessagingApi->push_message: %s\n' % e)


def read_urls_from_csv(filename: str) -> List[str]:
    """
    CSVファイルからURLを読み込んでリスト化する
    
    Args:
        filename: CSVファイルの名前（.csvは自動で付加）
    
    Returns:
        List[str]: URLのリスト
    
    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: URLカラムが存在しない場合
    """
    try:
        # ファイルパスの生成
        filepath = os.path.join('output', f'{filename}.csv')
        
        # ファイルの存在確認
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'ファイルが見つかりません: {filepath}')
        
        # URLを格納するリスト
        urls: List[str] = []
        
        # CSVファイルを読み込む
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            
            # ヘッダーを読み込む
            headers = next(reader, None)
            if not headers:
                return -1
                #raise ValueError('CSVファイルが空です')
            
            # URLカラムのインデックスを取得
            try:
                url_index = headers.index('URL')
            except ValueError:
                raise ValueError('URLカラムが見つかりません')
            
            # 各行からURLを取得
            for row in reader:
                if row and len(row) > url_index:
                    url = row[url_index].strip()
                    if url:  # 空でないURLのみ追加
                        urls.append(url)
        
        #logging.info(f'Readed {len(urls)} URLs')
        
        # 重複を除去（必要な場合）
        unique_urls = list(dict.fromkeys(urls))
        if len(unique_urls) != len(urls):
            logging.info(f'{len(urls) - len(unique_urls)}件の重複URLを除去しました')
        
        return unique_urls
        
    except Exception as e:
        logging.error(f'CSVファイルの読み込み中にエラーが発生しました: {str(e)}')
        raise


def export_to_csv(data_list, filename, encoding='utf-8-sig'):
    """
    データをCSVファイルに出力する（追記モード）
    
    Args:
        data_list: 出力するデータのリスト
        filename: 出力するファイルの基本名
        encoding: 文字エンコーディング（デフォルト: utf-8-sig）
    
    Returns:
        str: 保存されたファイルのパス
    """
    try:
        # 出力ディレクトリの作成
        output_dir = 'output'
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, f'{filename}.csv')
        
        # データの検証
        if not data_list:
            raise ValueError("データが空です")
        
        # ファイルが存在するかチェック
        file_exists = os.path.exists(filepath)
        
        # CSVファイルへの書き込み（追記モード）
        mode = 'a' if file_exists else 'w'
        with open(filepath, mode, newline='', encoding=encoding) as f:
            if isinstance(data_list[0], dict):
                # 辞書形式のデータの場合
                headers = list(data_list[0].keys())
                writer = csv.DictWriter(f, fieldnames=headers)
                # ヘッダーは新規ファイルの場合のみ書き込む
                if not file_exists:
                    writer.writeheader()
                writer.writerows(data_list)
            else:
                # リスト形式のデータの場合
                writer = csv.writer(f)
                writer.writerows(data_list)
        
        #logging.info(f'Saved CSV file path: {filepath}')
        return filepath
        
    except Exception as e:
        logging.error(f'CSVファイルの出力中にエラーが発生しました: {str(e)}')
        raise





#ファイル処理
def file_process(current_url,formatted_now,newItem,title,subtitle,daystart,dayend,gemini_text):
    #print("ファイル処理を行います")
    #ファイルの読み込み
    urls = read_urls_from_csv('crowdworks_data')
    if urls == -1:
        #CSVファイルへの書き込み
        data = [
            {
                'URL': current_url,
                'YMD': formatted_now,
                '新着': newItem,
                'タイトル': title,
                'カテゴリ': subtitle,
                '開始日': daystart,
                '終了日': dayend,
                'Gemini判定': gemini_text
            }
        ]        
        filepath = export_to_csv(data, 'crowdworks_data')    
    else:
        logging.info(f'Readed {len(urls)} URLs')
        #print(f"Readed {len(urls)} URLs")
        #print(urls)
        #for i, url in enumerate(urls, 1):
        #    print(f"{i}. {url}")
        
    # URLリストを変数として保持
    url_list = urls

    if current_url in url_list:
        index = url_list.index(current_url) + 1  # 1-based index
        print(f"{current_url}は登録済みです (リストの{index}件目)")
        return -1


    #CSVファイルへの書き込み
    try:
        data = [
            {
                'URL': current_url,
                'YMD': formatted_now,
                '新着': newItem,
                'タイトル': title,
                'カテゴリ': subtitle,
                '開始日': daystart,
                '終了日': dayend,
                'Gemini判定': gemini_text
            }
        ]
        
        filepath = export_to_csv(data, 'crowdworks_data')
        #print(f'データを {filepath} に保存しました')
        logging.info(f'Saved CSV file path: {filepath}')
        return 0
        
    except Exception as e:
        print(f'エラーが発生しました: {str(e)}')


def new_job(page,tag):    
    #新着案件の取得
    #新着タグの取得
    element = page.locator(f'#jobOfferSearchContainer div section ul li:nth-child({tag}) li.BwlmT')

    PRelement = page.locator(f'#jobOfferSearchContainer div section ul li:nth-child({tag}) li.RrGe7')
    time.sleep(1)
    #新着タグがある
    #if element.is_visible():
    if element.count() > 0 and element.first.is_visible() and PRelement.count() == 0:
        #newItem = element.text_content()
        newItem = element.first.text_content()
        #新着の場合
        if newItem == "新着":
            with page.expect_popup() as page1_info:
                #page.locator('xpath=//*[@id="jobOfferSearchContainer"]/div/div[3]/div[2]/section/ul/li[' + str(tag) + ']/div/div[2]/div[1]/h3/a').click()
                page.locator(f'#jobOfferSearchContainer div section ul li:nth-child({tag}) h3 a').click()
            time.sleep(2)
            page1 = page1_info.value
            time.sleep(2)
            element1 = page1.locator('xpath=//*[@id="job_offer_detail"]/div/div[1]')
            #element1 = page1.locator('#job_offer_detail div div:first-child')

            time.sleep(2)
            #詳細ページがある場合
            if element1.is_visible():
                pattern = r'^\s*$'   # 空白文字を含む空行
                # 2. 改行のみの行を削除
                cleaned_text = re.sub(pattern, '', element1.text_content(), flags=re.MULTILINE)
                #cleaned_text = re.sub(r'[\s　]+', '', cleaned_text)
                cleaned_text = re.sub(r'[^\S\n]+', '', cleaned_text)
                cleaned_text = cleaned_text.split('!function(d,s,id){')[0]
                
                #print("\n削除後のテキスト:")
                #print(cleaned_text)
                
                current_url = page1.url
                title = page1.locator('xpath=//*[@id="job_offer_detail"]/div/div[1]/section[1]/div[1]/h1')
                title = str(title.inner_html().split('<span class="subtitle">')[0].split('\n')[0])
                subtitle = page1.locator('xpath=//*[@id="job_offer_detail"]/div/div[1]/section[1]/div[1]/h1/span/a').text_content()
                daystart= re.sub(r'[\s ]+', '', cleaned_text.split('掲載日')[1].split('応募期限')[0])
                dayend = re.sub(r'[\s ]+', '', cleaned_text.split('応募期限')[1].split('応募状況')[0])

                page1.close()

                gemini_text = gemini_api(cleaned_text)
                time.sleep(1)
                gemini_text = re.sub(r'^\n', '', gemini_text)
                gemini_text = '\n' + gemini_text

                # フォーマット指定して日時
                now = datetime.now()
                formatted_now = now.strftime('%Y-%m-%d %H:%M:%S')
                
                result = f"url : {current_url} \
                    \nYMD : {formatted_now} \
                    \n新着？ : {newItem} \
                    \ntitle : {title} \
                    \ncategory : {subtitle} \
                    \nStart : {daystart} - End : {dayend}\
                    {gemini_text}"
                #result = re.sub(r'\n\s*\n', '', result)
                
                #print(result)

                return [current_url,formatted_now,newItem,title,subtitle,daystart,dayend,gemini_text]

            #詳細ページがない場合
            else:
                #print("詳細ページ取得エラー")
                return -1
        else:
            #print("[新着]以外：次の処理へ移ります")
            return -2
    #新着タグがない場合
    else:
        #print("一覧ページ取得エラー")
        return -3
    #新着案件の取得を終了



def gemini_api(text):
    # Geminiモデルの設定
    model = genai.GenerativeModel('gemini-1.5-flash')
    # 判定：CROWDWORKS_PROMPTを使い、textが初心者向けかどうか判定
    try:
        response = model.generate_content(CROWDWORKS_PROMPT + text)        
        if not response.candidates:
            error_info = {
                'block_reason': response.prompt_feedback.block_reason,
                'safety_ratings': response.prompt_feedback.safety_ratings,
                'prompt': text[:100] + '...'  # プロンプトの先頭100文字
            }
            print(f"API Block Details: {error_info}")
            return "APIエラー: 詳細はログを確認してください"
            
        return response.text
        
    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        return "APIエラー: " + str(e)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--window-size=1200,1200'])
        context = browser.new_context(viewport={"width": 1200, "height": 1200})
        page = context.new_page()
        # CrowdWorks のログインページにアクセス
        page.goto("https://crowdworks.jp/login")
        
        time.sleep(3)
        page.get_by_label("メールアドレス").click()
        page.get_by_label("メールアドレス").fill("sinzy0925@gmail.com")
        time.sleep(1)
        page.get_by_label("パスワード").click()
        page.get_by_label("パスワード").fill("5l7o8qaDcloud")
        time.sleep(1)
        page.get_by_role("button", name="ログイン", exact=True).click()
        time.sleep(2)
        page.locator("#norman-header-section").get_by_role("link", name="仕事を探す").click()
        time.sleep(2)
        page.get_by_role("link", name="ライティング・記事作成").first.click()
        time.sleep(2)
        page.locator("section").filter(has_text="検索 ").get_by_role("combobox").select_option("new")
        time.sleep(2)
        
        #新着案件の取得
        for i in range(1,10):
            list_new_job = new_job(page,i)
            if list_new_job == -1:
                print("詳細ページ取得エラー")
            elif list_new_job == -2:
                print("[新着なし]：次の処理へ移ります")
            elif list_new_job == -3:
                print("一覧ページ[新着以外]：次の処理へ移ります")
            else:
                current_url = list_new_job[0]
                formatted_now = list_new_job[1]
                newItem = list_new_job[2]
                title = list_new_job[3]
                subtitle = list_new_job[4]
                daystart = list_new_job[5]
                dayend = list_new_job[6]
                gemini_text = list_new_job[7]
        
                #ファイル処理
                file_result = file_process(current_url,formatted_now,newItem,title,subtitle,daystart,dayend,gemini_text)
                if file_result == -1:                    
                    print("StopLoop : 新着案件なしのため取得を終了します\n")
                    #break
                else:
                    #print("新規登録しました")
                    #LINE送信logging.info(f'Saved CSV file path: {filepath}')
                    linemsg = (f"{newItem}\
                               \n{formatted_now}\
                               \nURL : {current_url}\
                               \nタイトル : {title}\
                               \nカテゴリ : {subtitle}\
                               \n掲載日 : {daystart}\
                               \n応募期限日 : {dayend}\
                               \n{gemini_text}")
                    send_line(linemsg)


        time.sleep(1)
        browser.close()

if __name__ == "__main__":
    main()

