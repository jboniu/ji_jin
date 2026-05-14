# 鏀粯瀹濆熀閲戣嚜鍔ㄥ垎鏋愮郴缁?
褰撳墠闃舵鐩爣锛氳窇閫氭湰鍦?Python 鑴氭湰锛屾姄鍙栨柊闂诲苟鐢熸垚涓€浠?AI Markdown 鍒嗘瀽鎶ュ憡銆?
## 褰撳墠鏂囦欢
- `fetch_news.py`锛氭姄鍙栧叕寮€璐㈢粡鏂伴椈
- `analyze_fund.py`锛氳皟鐢ㄥ吋瀹?OpenAI 鎺ュ彛鐨勫ぇ妯″瀷鐢熸垚鍩洪噾鍒嗘瀽
- `generate_report.py`锛氱敓鎴?Markdown 鎶ュ憡
- `portfolio.json`锛氭墜鍔ㄧ淮鎶ょ殑鎸佷粨缁撴瀯
- `portfolio.py`锛氳鍙栧拰鏍煎紡鍖栨寔浠撴憳瑕?- `reports/`锛氭姤鍛婅緭鍑虹洰褰?
## 鏈湴鍑嗗
1. 鍒涘缓铏氭嫙鐜锛歚python -m venv .venv`
2. 瀹夎渚濊禆锛歚.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. 澶嶅埗鐜鍙橀噺妯℃澘锛氬皢 `.env.example` 鍙﹀瓨涓?`.env`
4. 鍦?`.env` 涓～鍐欐ā鍨嬮厤缃?5. 鍏堟祴璇曟姄鏂伴椈锛歚.\.venv\Scripts\python.exe .\fetch_news.py`
6. 鍐嶇敓鎴愭姤鍛婏細`.\.venv\Scripts\python.exe .\generate_report.py`

## 鎸佷粨涓€у寲杈撳叆
褰撳墠鏀寔閫氳繃 `portfolio.json` 鎵嬪姩缁存姢鎸佷粨缁撴瀯銆?
鍙厛鍗曠嫭娴嬭瘯璇诲彇鏁堟灉锛?
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\.venv\Scripts\python.exe .\portfolio.py
```

褰撳墠鎶ュ憡浼氳嚜鍔ㄦ妸 `portfolio.json` 鐨勬寔浠撴憳瑕佷竴璧蜂紶缁?AI锛屽洜姝ゆ姤鍛婂唴瀹逛細鏇磋创杩戜綘鐨勭粍鍚堢粨鏋勩€?褰撳墠鏃ユ姤宸插崌绾т负鈥滄姇璧勪笓瀹惰瑙掆€濈殑鐗堟湰锛岄噸鐐硅緭鍑猴細
- 杩戜竴鍛ㄥ競鍦哄洖椤?- 浠婃棩 15:00 鍓嶉噸鐐瑰叧娉?- 鍔犱粨瑙傚療
- 鍑忎粨瑙傚療
- 鎸佹湁瑙傚療

## 澶氱敤鎴峰噯澶?褰撳墠宸叉敮鎸侀€氳繃 `users.json` 缁存姢澶氫釜鐢ㄦ埛銆?
姣忎釜鐢ㄦ埛鍙厤缃細
- `user_id`锛氱敤鎴锋爣璇?- `owner`锛氱敤鎴峰悕绉?- `email_to`锛氳鐢ㄦ埛鐨勬敹浠堕偖绠卞垪琛?- `positions`锛氳鐢ㄦ埛鑷繁鐨勬寔浠?
褰撳墠涓绘祦绋嬩細浼樺厛璇诲彇 `users.json`锛?- 濡傛灉閰嶇疆浜嗗涓敤鎴凤紝浼氶€愪釜鐢熸垚鎶ュ憡
- 姣忎唤鎶ュ憡浼氭寜璇ョ敤鎴疯嚜宸辩殑 `email_to` 鍙戦€?- 鎶ュ憡鏂囦欢鍚嶄腑浼氬甫涓婄敤鎴峰悕绉帮紝渚夸簬鍖哄垎

鍙厛鍗曠嫭娴嬭瘯璇诲彇鏁堟灉锛?
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\.venv\Scripts\python.exe .\portfolio.py
```

## 鎺ㄨ崘閰嶇疆
褰撳墠榛樿鎺ㄨ崘浣跨敤鏅鸿氨鍏嶈垂妯″瀷锛?
```env
LLM_PROVIDER=zhipu
OPENAI_API_KEY=浣犵殑鏅鸿氨API Key
OPENAI_MODEL=glm-4.7-flash
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

濡傛灉鍚庣画瑕佸垏鍥?OpenAI锛屽彲鏀规垚锛?
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=浣犵殑OpenAI API Key
OPENAI_MODEL=gpt-4.1-mini
```

## 閭鍙戦€侀厤缃?濡傛灉浣犲笇鏈涙姤鍛婄敓鎴愬悗鑷姩鍙戦€侀偖绠憋紝鍙互鍦?`.env` 涓ˉ鍏咃細

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=浣犵殑鍙戜欢閭
SMTP_PASSWORD=浣犵殑SMTP鎺堟潈鐮?SMTP_USE_SSL=true
EMAIL_FROM=浣犵殑鍙戜欢閭
EMAIL_TO=浣犵殑鏀朵欢閭
```

璇存槑锛?- `SMTP_PASSWORD` 涓€鑸笉鏄偖绠辩櫥褰曞瘑鐮侊紝鑰屾槸 SMTP 鎺堟潈鐮?- 甯歌閭濡?QQ銆?63銆佷紒涓氶偖绠遍兘鏀寔 SMTP
- 濡傛灉娌℃湁閰嶇疆杩欎簺瀛楁锛岃剼鏈細鍙敓鎴愭湰鍦版姤鍛婏紝涓嶄細涓柇

## 手动运行
当前项目已停用“交易日自动执行日报脚本”。

手动运行单次日报：
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\run_daily_report.bat
```

如果这台电脑之前注册过旧的 Windows 任务计划，可执行：
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
powershell -ExecutionPolicy Bypass -File .\unregister_daily_task.ps1
```

说明：
- 保留手动执行入口：`run_daily_report.bat`
- `register_daily_task.ps1` 已不再注册自动任务
- `.env` 里的 `TASK_TIME`、`TASK_WEEKDAYS` 仅作为历史配置保留，不再自动生效

## 褰撳墠鐘舵€?椤圭洰宸叉帴鍏ュ熀纭€鏂伴椈鎶撳彇鍜?AI 鍒嗘瀽閫昏緫锛屽苟鏀寔鍒囨崲鍒版櫤璋卞吋瀹规帴鍙ｃ€?
## 鏃ュ織涓庡け璐ラ噸璇?- 杩愯鏃ュ織浼氬啓鍏?`logs/fund_analysis.log`
- AI 鍒嗘瀽澶辫触鏃朵細鑷姩閲嶈瘯 2 娆?- 閭欢鍙戦€佸け璐ユ椂浼氳嚜鍔ㄩ噸璇?2 娆?- 鍗充娇 AI 鎴栭偖浠跺け璐ワ紝鏃ュ織閲屼篃浼氫繚鐣欓敊璇粏鑺傦紝鏂逛究鎺掓煡
