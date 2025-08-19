from openai import OpenAI
import json
import re
from datetime import datetime
from dotenv import load_dotenv
import os

class ESContentGenerator:
    def __init__(self, api_key=None):
        load_dotenv()  # .envファイルから環境変数を読み込む
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("APIキーが設定されていません。環境変数OPENAI_API_KEYを確認してください。")
        self.client = OpenAI(api_key=api_key)
        self.history = []
    
    def get_input_with_validation(self, prompt, choices=None, input_type="text"):
        """汎用入力・検証関数"""
        while True:
            if choices:
                print(f"\n=== {prompt} ===")
                for key, value in choices.items():
                    if isinstance(value, dict):
                        desc = value.get('description', value.get('purpose', value.get('name', '')))
                        print(f"{key}: {value.get('name', key)} - {desc}")
                    else:
                        print(f"{key}: {value}")
                
                choice = input(f"\n選択してください (1-{len(choices)}): ").strip()
                if choice in choices:
                    return choice, choices[choice]
                else:
                    print(f"範囲外の番号です。1-{len(choices)}の番号を入力してください。（入力値: {choice}）")
            
            elif input_type == "number":
                try:
                    num = int(input(f"{prompt}: ").strip())
                    if num > 0:
                        return num
                    else:
                        print("1以上の数値を入力してください。")
                except ValueError:
                    print("数値を入力してください。")
            
            else:
                return input(f"{prompt}: ").strip()
    
    def get_company_info(self):
        """企業情報を収集"""
        print("\n=== 志望企業情報入力 ===")
        print("すべての項目は任意入力です。空欄でもOKです！")
        
        fields = [
            ('company_name', '企業名', '志望企業'),
            ('company_url', '企業ホームページURL（任意）', ''),
            ('company_philosophy', '企業理念・ビジョン（知っている場合）', ''),
            ('company_values', '企業の価値観・大切にしていること', ''),
            ('business_description', '主な事業内容・サービス', ''),
            ('company_culture', '企業文化・働く環境の特徴', ''),
            ('ideal_candidate', '求める人材像（募集要項から）', '')
        ]
        
        company_info = {}
        for key, prompt, default in fields:
            value = self.get_input_with_validation(prompt) or default
            company_info[key] = value
        
        # URLが提供された場合、企業情報を自動取得
        if company_info['company_url']:
            print("企業ホームページから情報を取得中...")
            web_info = self.fetch_company_info(company_info['company_url'])
            if web_info:
                company_info['web_scraped_info'] = web_info
                print(" 企業情報を取得しました")
            else:
                print("企業情報の自動取得に失敗しました。手動入力情報を使用します。")
        
        # 入力確認メッセージ
        filled_items = sum(1 for k, v in company_info.items() if v and k not in ['company_name', 'web_scraped_info'])
        msg = "一般的な" if filled_items == 0 else f"{filled_items}項目の企業情報を使用した特化型"
        print(f"\n{company_info['company_name']}向けの{msg}コンテンツを作成します。")
        
        return company_info
    
    def fetch_company_info(self, url):
        """企業ホームページから情報を取得（簡易版）"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title')
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            
            return {
                'title': title.get_text().strip() if title else "",
                'description': meta_desc.get('content', '').strip() if meta_desc else "",
                'content_summary': ' '.join(soup.get_text().split())[:1000]
            }
            
        except Exception as e:
            print(f"企業情報取得エラー: {str(e)}")
            return None
    
    def get_user_input(self):
        """ユーザー情報を詳細に収集"""
        print("=== あなたの情報入力 ===")
        
        fields = [
            ('strength', 'あなたの強み（複数可、カンマ区切り）'),
            ('experience', 'その強みを活かした具体的な経験・エピソード'),
            ('job_role', '志望職種'),
            ('achievements', '特に誇れる成果・実績（数値があれば具体的に）'),
            ('skills', '持っているスキル・資格'),
            ('personality', 'あなたの性格・人柄'),
            ('motivation', 'この職種を志望する理由・動機')
        ]
        
        return {key: self.get_input_with_validation(prompt) for key, prompt in fields}
    
    def select_content_type(self):
        """作成するコンテンツタイプを選択"""
        content_types = {
            "1": {"name": "自己PR", "description": "あなたの強みや経験をアピール"},
            "2": {"name": "志望動機", "description": "なぜその企業・職種を志望するのか"},
            "3": {"name": "カスタムES質問", "description": "ESの具体的な質問に回答"}
        }
        return self.get_input_with_validation("作成するコンテンツ選択", content_types)
    
    def get_es_question(self):
        """ES質問を取得"""
        print("\n=== ES質問入力 ===")
        print("ESで聞かれている質問文をそのまま貼り付けてください")
        print("例: 「学生時代に最も力を入れて取り組んだことについて教えてください（400字以内）」")
        
        es_question = self.get_input_with_validation("\nES質問")
        return es_question or "あなたの経験や取り組みについて教えてください。"
    
    def select_pr_style(self):
        """文章スタイルを選択"""
        styles = {
            "1": {"name": "論理的・分析型", "tone": "論理的で分析的、データに基づいた表現"},
            "2": {"name": "情熱・エネルギッシュ型", "tone": "情熱的で積極的、エネルギッシュな表現"},
            "3": {"name": "協調・チームワーク型", "tone": "協調性を重視し、チームワークを強調した表現"},
            "4": {"name": "創造・イノベーション型", "tone": "創造性や革新性を前面に出した表現"},
            "5": {"name": "誠実・信頼型", "tone": "誠実さや信頼性を重視した表現"}
        }
        return self.get_input_with_validation("文章スタイル選択", styles)[1]
    
    def select_length(self):
        """文字数を選択"""
        lengths = {
            "1": {"range": "200-250文字", "purpose": "履歴書用（簡潔版）"},
            "2": {"range": "300-350文字", "purpose": "一般的な自己PR"},
            "3": {"range": "400-500文字", "purpose": "詳細版（面接対策用）"},
            "4": {"range": "カスタム", "purpose": "任意の文字数を指定"}
        }
        
        choice, selected = self.get_input_with_validation("文字数選択", lengths)
        
        if choice == "4":
            custom_length = self.get_input_with_validation("希望する文字数を入力してください", input_type="number")
            return {"range": f"{custom_length}文字程度", "purpose": f"カスタム設定（{custom_length}文字）"}
        
        return selected
    
    def create_system_prompt(self, content_type, company_info, style, length, es_question=None):
        """システムプロンプトを作成"""
        
        # 企業情報を自然な文章で整理
        company_context = self.format_company_context(company_info)
        length_guide = self.format_length_guide(length['range'])
        tone_guide = self.format_tone_guide(style['tone'])
        
        if content_type == "1":  # 自己PR
            return f"""経験豊富な就職コンサルタントとして、{company_info['company_name']}に向けた印象的な自己PRを作成してください。

{company_context}

文章は{length_guide}で、{tone_guide}でお願いします。

自己PRでは、まず結論として自分の強みを明確に示し、その根拠となる具体的な経験やエピソードを交え、最終的にその企業でどのように活躍できるかまで繋げてください。読み手が「この人と一緒に働いてみたい」と思えるような魅力的な内容にしてください。"""
        
        elif content_type == "2":  # 志望動機
            return f"""就職活動のプロとして、{company_info['company_name']}への心に響く志望動機を作成してください。

{company_context}

文章は{length_guide}で、{tone_guide}でお願いします。

志望動機では、なぜこの業界を選んだのか、数ある企業の中でなぜこの会社なのか、そして将来どのように貢献していきたいかという流れで構成してください。ありきたりな表現ではなく、個人の体験や価値観が感じられる内容にしてください。"""
        
        else:  # カスタムES質問
            return f"""就職活動の専門家として、以下の質問に対する魅力的で印象深い回答を作成してください。

質問: {es_question}

{company_context}

文章は{length_guide}で、{tone_guide}でお願いします。

質問の真意を理解し、採用担当者が求めている人物像を意識して回答してください。具体的なエピソードを通じて人柄や能力が伝わるよう、ストーリー性のある構成にしてください。"""

    def format_company_context(self, company_info):
        """企業情報を自然な文章として整理"""
        context_parts = []
        
        if company_info['company_philosophy']:
            context_parts.append(f"この企業は「{company_info['company_philosophy']}」という理念を掲げています。")
        
        if company_info['company_values']:
            context_parts.append(f"企業として「{company_info['company_values']}」を大切にしています。")
        
        if company_info['business_description']:
            context_parts.append(f"主な事業は{company_info['business_description']}です。")
        
        if company_info['company_culture']:
            context_parts.append(f"職場環境の特徴として{company_info['company_culture']}があります。")
        
        if company_info['ideal_candidate']:
            context_parts.append(f"求める人材像は{company_info['ideal_candidate']}です。")
        
        if context_parts:
            return "企業について: " + " ".join(context_parts)
        else:
            return f"{company_info['company_name']}についての詳細情報は限られていますが、一般的な企業研究をもとに魅力的な文章を作成してください。"

    def format_length_guide(self, length_range):
        """文字数指定を自然な表現に変換"""
        return f"{length_range}を目安とし、内容を優先しつつ適切な長さ"
    
    def format_tone_guide(self, tone):
        """トーン指定を自然な表現に変換"""
        return f"{tone}を心がけ、読み手に親しみやすく印象に残る文章"
    
    def generate_content(self, user_info, company_info, style, length, content_type, es_question=None):
        """コンテンツを生成"""
        system_prompt = self.create_system_prompt(content_type, company_info, style, length, es_question)
        
        content_names = {"1": "自己PR文", "2": "志望動機", "3": "ES回答"}
        content_name = content_names[content_type]
        
        user_prompt = f"""以下は応募者の情報です。この方の魅力を最大限に引き出して、{company_info['company_name']}向けの{content_name}を作成してください。

応募者について:
この方の最大の強みは「{user_info['strength']}」で、具体的には{user_info['experience']}という経験があります。

志望している職種は{user_info['job_role']}で、これまでに{user_info['achievements']}という実績を上げています。

保有スキルとしては{user_info['skills']}があり、性格的には{user_info['personality']}という特徴があります。

この職種への動機として、{user_info['motivation']}という想いを持っています。

この情報をもとに、応募者の人柄と能力が伝わり、{company_info['company_name']}で活躍する姿が想像できるような魅力的な文章を作成してください。この人ならではの個性が光る内容にしてください。"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"
    
    def call_gpt(self, prompt, temperature=0.3):
        """GPT呼び出しの共通関数"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"エラー: {str(e)}"
    
    def analyze_pr(self, content_text, content_type_name):
        """生成されたコンテンツを分析・評価"""
        prompt = f"""就職活動の経験豊富なアドバイザーとして、以下の{content_type_name}について率直で建設的なフィードバックをお願いします。

{content_type_name}:
{content_text}

採用担当者の視点から見て、この文章の良い点と改善できる点を具体的に教えてください。また、より印象的にするためのアドバイスも含めてください。

文字数や構成バランスについても触れていただけると助かります。5点満点などの点数は不要で、具体的で実践的なアドバイスをお願いします。"""
        return self.call_gpt(prompt)
    
    def generate_variations(self, user_info, company_info, original_content, content_type_name):
        """企業特化のバリエーション版を生成"""
        prompt = f"""以下の{content_type_name}をベースに、{company_info['company_name']}向けに3つの異なるアプローチで書き直してください。

元の{content_type_name}:
{original_content}

応募者の情報:
- 強み: {user_info['strength']}
- 経験: {user_info['experience']}  
- 志望職種: {user_info['job_role']}

3つのアプローチ:

1. 「企業理念重視版」
この企業の価値観や理念との共感を前面に出し、価値観の一致をアピールする書き方

2. 「実績・成果重視版」  
具体的な数字や成果を強調し、即戦力としての能力をアピールする書き方

3. 「人柄・協調性重視版」
チームワークやコミュニケーション能力など、一緒に働きたいと思われる人柄をアピールする書き方

それぞれ同じような文字数で、企業名を自然に織り込んで作成してください。どのバージョンも個性的で印象に残る内容にしてください。"""
        return self.call_gpt(prompt, temperature=0.8)
    
    def save_to_file(self, content, company_name):
        """結果をファイルに保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-_\.]', '_', company_name)
        filename = f"ES_{safe_name}_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nファイルに保存しました: {filename}")
        except Exception as e:
            print(f"保存エラー: {str(e)}")
    
    def handle_menu_choice(self, choice, user_info, company_info, generated_content, content_info, content_type, es_question, style, length):
        """メニュー選択の処理"""
        if choice == "1":
            print(f"\n文章分析・改善提案:")
            analysis = self.analyze_pr(generated_content, content_info['name'])
            print(analysis)
            return generated_content, content_info, es_question
        
        elif choice == "2":
            print(f"\n{company_info['company_name']}特化バリエーション版生成中...")
            variations = self.generate_variations(user_info, company_info, generated_content, content_info['name'])
            print(f"\n{company_info['company_name']}向け{content_info['name']}バリエーション版:")
            print(variations)
            return generated_content, content_info, es_question
        
        elif choice == "3":
            #保存データの整理をより自然な文章形式に変更
            content_for_save = f"""【{company_info['company_name']}向け{content_info['name']}】

{f"質問: {es_question}" if es_question else ""}

{generated_content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

作成情報:
対象企業: {company_info['company_name']}
コンテンツタイプ: {content_info['name']}
文章スタイル: {style['name']}
目安文字数: {length['range']}
作成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}

企業について:
{self.format_company_info_for_save(company_info)}

応募者について:
{self.format_user_info_for_save(user_info)}
"""
            self.save_to_file(content_for_save, company_info['company_name'])
            return generated_content, content_info, es_question
        
        elif choice == "4":
            print("\n" + "="*50)
            self.run()
            return None, None, None  # 新しいセッション開始の印
        
        elif choice in ["5", "6"]:
            if choice == "5":
                print(f"\n{company_info['company_name']}向けの別コンテンツを作成...")
                new_content_type, new_content_info = self.select_content_type()
                new_es_question = self.get_es_question() if new_content_type == "3" else None
                new_style = self.select_pr_style()
                new_length = self.select_length()
            else:  # choice == "6"
                print(f"\n別のスタイルで{content_info['name']}を再生成...")
                new_content_type, new_content_info = content_type, content_info
                new_es_question = es_question
                new_style = self.select_pr_style()
                new_length = self.select_length()
            
            new_content = self.generate_content(user_info, company_info, new_style, new_length, new_content_type, new_es_question)
            
            print(f"\n新しい{company_info['company_name']}向け{new_content_info['name']}:")
            print("="*60)
            if new_es_question:
                print(f"質問: {new_es_question}")
            print(new_content)
            print("="*60)
            
            return new_content, new_content_info, new_es_question
        
        return generated_content, content_info, es_question

    def format_company_info_for_save(self, company_info):
        """保存用に企業情報を自然な文章でフォーマット"""
        info_parts = []
        
        if company_info['company_philosophy']:
            info_parts.append(f"企業理念: {company_info['company_philosophy']}")
        if company_info['company_values']:
            info_parts.append(f"大切にしている価値観: {company_info['company_values']}")
        if company_info['business_description']:
            info_parts.append(f"事業内容: {company_info['business_description']}")
        if company_info['company_culture']:
            info_parts.append(f"企業文化: {company_info['company_culture']}")
        if company_info['ideal_candidate']:
            info_parts.append(f"求める人材: {company_info['ideal_candidate']}")
        
        return "\n".join(info_parts) if info_parts else "詳細情報は未入力"

    def format_user_info_for_save(self, user_info):
        """保存用に応募者情報を自然な文章でフォーマット"""
        return f"""強み: {user_info['strength']}
具体的経験: {user_info['experience']}
志望職種: {user_info['job_role']}
主な実績: {user_info['achievements']}
保有スキル: {user_info['skills']}
性格・人柄: {user_info['personality']}
志望動機: {user_info['motivation']}"""
    
    def run(self):
        """メイン実行フロー"""        
        #情報収集・設定
        user_info = self.get_user_input()
        company_info = self.get_company_info()
        content_type, content_info = self.select_content_type()
        es_question = self.get_es_question() if content_type == "3" else None
        style = self.select_pr_style()
        length = self.select_length()
        
        print(f"\n{company_info['company_name']}向けの{content_info['name']}を生成中...")
        
        #コンテンツ生成
        generated_content = self.generate_content(user_info, company_info, style, length, content_type, es_question)
        
        print("\n" + "="*60)
        print(f"{company_info['company_name']}向け{content_info['name']}")
        if es_question:
            print(f"質問: {es_question}")
        print("="*60)
        print(generated_content)
        print("="*60)
        
        # 8. 追加機能の選択
        while True:
            print("\n追加オプション:")
            options = ["文章分析・改善提案を見る", "バリエーション版を生成", "ファイルに保存", 
                      "別の企業向けに作成", "同じ企業で別のコンテンツを作成", "同じ企業・コンテンツで別スタイルを試す"]
            for i, option in enumerate(options, 1):
                print(f"{i}: {option}")
            print("0: 終了")
            
            choice = input("\n選択してください (0-6): ").strip()
            
            if choice == "0":
                print(f"{company_info['company_name']}への応募、頑張ってください！")
                break
            elif choice in map(str, range(1, 7)):
                result = self.handle_menu_choice(choice, user_info, company_info, generated_content, 
                                               content_info, content_type, es_question, style, length)
                if result[0] is None:  # 新しいセッション開始
                    break
                generated_content, content_info, es_question = result
            else:
                print(f"範囲外の番号です。0-6の番号を入力してください。（入力値: {choice}）")

# 使用例
if __name__ == "__main__":
    print("===オールインワンES作成ツール===")
    print("必要なライブラリ: pip install openai requests beautifulsoup4")
    print("=" * 50)
    
    try:
        generator = ESContentGenerator()#環境変数を参照する
        generator.run()
    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")
        print("\nトラブルシューティング:")
        print("1. APIキーが正しいか確認してください")
        print("2. OpenAIアカウントにクレジットがあるか確認してください")
        print("3. インターネット接続を確認してください")
        print("4. 必要なライブラリがインストールされているか確認してください")