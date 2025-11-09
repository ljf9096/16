import requests
import concurrent.futures
import datetime
import re
import time
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===== 配置参数 =====
MAX_WORKERS = 50
TIMEOUT = 2
MAX_RETRIES = 2

# ===== 原始URL列表 =====
urls = [
    "http://1.192.12.1:9901",
    "http://1.192.248.1:9901",
    "http://1.194.52.1:10086",
    # ... 这里放置您所有的URL，为了简洁我只保留几个示例
    "http://61.184.128.1:9901",
    "http://61.53.90.1:9901",
    "http://61.54.14.1:9901"
]

# ===== 创建会话对象 =====
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# ===== 工具函数 =====
def modify_urls(url):
    """修改URL，将IP的最后一位改为1-255"""
    modified_urls = []
    try:
        # 解析URL
        if url.startswith("http://"):
            base = "http://"
            rest = url[7:]
        elif url.startswith("https://"):
            base = "https://"
            rest = url[8:]
        else:
            return modified_urls
        
        # 提取IP和端口
        ip_end_index = rest.find(":")
        if ip_end_index == -1:
            return modified_urls
            
        ip_str = rest[:ip_end_index]
        port_and_path = rest[ip_end_index:]
        
        # 解析IP地址
        ip_parts = ip_str.split(".")
        if len(ip_parts) != 4:
            return modified_urls
            
        base_ip = ".".join(ip_parts[:3])
        ip_end = "/iptv/live/1000.json?key=txiptv"
        
        # 生成修改后的URL
        for i in range(1, 256):
            modified_ip = f"{base_ip}.{i}"
            modified_url = f"{base}{modified_ip}{port_and_path}{ip_end}"
            modified_urls.append(modified_url)
            
    except Exception as e:
        print(f"修改URL时出错: {e}")
        
    return modified_urls

def is_url_accessible(url):
    """检查URL是否可访问"""
    session = create_session()
    try:
        response = session.get(url, timeout=TIMEOUT, verify=False)
        if response.status_code == 200:
            return url
    except Exception:
        pass
    finally:
        session.close()
    return None

def normalize_channel_name(name):
    """标准化频道名称"""
    if not name:
        return ""
    
    # 替换中文名称
    name = name.replace("cctv", "CCTV")
    name = name.replace("中央", "CCTV")
    name = name.replace("央视", "CCTV")
    
    # 移除不需要的字符和词语
    remove_words = ["高清", "超高", "HD", "标清", "频道", "-", " ", "PLUS", "＋", "(", ")", "台"]
    for word in remove_words:
        name = name.replace(word, "")
    
    # CCTV频道标准化
    cctv_patterns = [
        (r"CCTV1综合", "CCTV1"),
        (r"CCTV2财经", "CCTV2"),
        (r"CCTV3综艺", "CCTV3"),
        (r"CCTV4国际", "CCTV4"),
        (r"CCTV4中文国际", "CCTV4"),
        (r"CCTV4欧洲", "CCTV4"),
        (r"CCTV5体育", "CCTV5"),
        (r"CCTV6电影", "CCTV6"),
        (r"CCTV7军事", "CCTV7"),
        (r"CCTV7军农", "CCTV7"),
        (r"CCTV7农业", "CCTV7"),
        (r"CCTV7国防军事", "CCTV7"),
        (r"CCTV8电视剧", "CCTV8"),
        (r"CCTV9记录", "CCTV9"),
        (r"CCTV9纪录", "CCTV9"),
        (r"CCTV10科教", "CCTV10"),
        (r"CCTV11戏曲", "CCTV11"),
        (r"CCTV12社会与法", "CCTV12"),
        (r"CCTV13新闻", "CCTV13"),
        (r"CCTV新闻", "CCTV13"),
        (r"CCTV14少儿", "CCTV14"),
        (r"CCTV15音乐", "CCTV15"),
        (r"CCTV16奥林匹克", "CCTV16"),
        (r"CCTV17农业农村", "CCTV17"),
        (r"CCTV17农业", "CCTV17"),
        (r"CCTV5+体育赛视", "CCTV5+"),
        (r"CCTV5+体育赛事", "CCTV5+"),
        (r"CCTV5+体育", "CCTV5+")
    ]
    
    for pattern, replacement in cctv_patterns:
        name = re.sub(pattern, replacement, name)
    
    # 正则表达式清理
    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
    
    return name.strip()

def process_single_url(url):
    """处理单个URL，获取频道信息"""
    session = create_session()
    channels = []
    
    try:
        # 获取JSON数据
        response = session.get(url, timeout=TIMEOUT, verify=False)
        if response.status_code != 200:
            return channels
            
        json_data = response.json()
        
        # 提取基础URL
        if url.startswith("http://"):
            base_url = "http://" + url.split("//")[1].split("/")[0]
        else:
            base_url = "https://" + url.split("//")[1].split("/")[0]
        
        # 解析频道数据
        if 'data' in json_data and isinstance(json_data['data'], list):
            for item in json_data['data']:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    urlx = item.get('url', '')
                    
                    if not name or not urlx:
                        continue
                    
                    # 处理URL
                    if ',' in urlx:
                        continue  # 跳过包含逗号的URL
                    
                    if urlx.startswith(('http://', 'https://', 'udp://', 'rtp://')):
                        final_url = urlx
                    else:
                        final_url = base_url + urlx
                    
                    # 标准化频道名称
                    normalized_name = normalize_channel_name(name)
                    
                    if normalized_name and final_url:
                        channels.append((normalized_name, final_url))
                        
    except Exception as e:
        pass
    finally:
        session.close()
        
    return channels

def main():
    print("开始处理URL...")
    start_time = time.time()
    
    # 第一步：预处理URL
    print("1. 预处理URL...")
    processed_urls = set()
    for url in urls:
        url = url.strip()
        if not url:
            continue
            
        # 将IP最后一位改为1
        try:
            if url.startswith("http://"):
                base = "http://"
                rest = url[7:]
            else:
                base = "https://"
                rest = url[8:]
                
            ip_end_index = rest.find(":")
            if ip_end_index != -1:
                ip_str = rest[:ip_end_index]
                port_and_path = rest[ip_end_index:]
                ip_parts = ip_str.split(".")
                if len(ip_parts) == 4:
                    base_ip = ".".join(ip_parts[:3])
                    processed_url = f"{base}{base_ip}.1{port_and_path}"
                    processed_urls.add(processed_url)
        except Exception:
            continue
    
    print(f"预处理后得到 {len(processed_urls)} 个基础URL")
    
    # 第二步：生成测试URL并检查可访问性
    print("2. 生成并测试URL...")
    all_test_urls = []
    for base_url in processed_urls:
        all_test_urls.extend(modify_urls(base_url))
    
    print(f"生成了 {len(all_test_urls)} 个测试URL")
    
    valid_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(is_url_accessible, url): url for url in all_test_urls}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if (i + 1) % 1000 == 0:
                print(f"已测试 {i + 1}/{len(all_test_urls)} 个URL")
                
            result = future.result()
            if result:
                valid_urls.append(result)
    
    print(f"找到 {len(valid_urls)} 个有效URL")
    
    # 第三步：从有效URL获取频道信息
    print("3. 获取频道信息...")
    all_channels = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_url, url): url for url in valid_urls}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if (i + 1) % 100 == 0:
                print(f"已处理 {i + 1}/{len(valid_urls)} 个有效URL")
                
            channels = future.result()
            if channels:
                all_channels.extend(channels)
    
    # 去重
    unique_channels = list(set(all_channels))
    print(f"获取到 {len(unique_channels)} 个唯一频道")
    
    # 第四步：保存结果
    print("4. 保存结果...")
    
    # 保存有效URL
    today = datetime.date.today()
    with open("ip.txt", 'w', encoding='utf-8') as f:
        f.write(f"{today}更新\n")
        for url in valid_urls:
            f.write(url + "\n")
    
    # 保存频道列表
    with open("tvlist.txt", 'w', encoding='utf-8') as f:
        for name, url in unique_channels:
            f.write(f"{name},{url}\n")
    
    # 打印统计信息
    end_time = time.time()
    print(f"\n处理完成！")
    print(f"总耗时: {end_time - start_time:.2f} 秒")
    print(f"有效URL数量: {len(valid_urls)}")
    print(f"频道数量: {len(unique_channels)}")
    print(f"结果已保存到 ip.txt 和 tvlist.txt")

if __name__ == "__main__":
    main()
