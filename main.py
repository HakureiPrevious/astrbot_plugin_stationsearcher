import json
import os
from typing import List, Dict, Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class StationSearcherPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取插件数据目录
        self.plugin_data_path = os.path.join(get_astrbot_data_path(), "plugin_data", self.name)
        # 确保插件数据目录存在
        os.makedirs(self.plugin_data_path, exist_ok=True)
        
        # 数据库文件路径
        self.db_file = os.path.join(self.plugin_data_path, "stations_database.json")
        
        # 从插件目录复制最新的数据库文件（每次启动都更新）
        import shutil
        default_db = os.path.join(os.path.dirname(__file__), "stations_database.json")
        if os.path.exists(default_db):
            shutil.copy(default_db, self.db_file)
        else:
            # 如果默认数据库也不存在，创建一个空的
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump({"stations": []}, f, ensure_ascii=False, indent=2)
        
        # 加载数据库
        self.stations_db = self._load_database()
    
    def _load_database(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载车站数据库"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"stations": []}
    
    def _save_database(self) -> bool:
        """保存车站数据库"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.stations_db, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            return False
    
    def _search_station(self, station_name: str) -> List[Dict[str, Any]]:
        """搜索车站"""
        results = []
        for station in self.stations_db.get("stations", []):
            if station_name in station.get("name", ""):
                results.append(station)
        return results
    
    @filter.command("station")
    async def station_search(self, event: AstrMessageEvent, station_name: str):
        """
        搜索车站信息
        用法: station <车站名称> 或 /station <车站名称>
        """
        if not station_name:
            yield event.plain_result("请输入车站名称，用法: station <车站名称>")
            return
        
        # 搜索车站
        results = self._search_station(station_name)
        
        if not results:
            yield event.plain_result(f"未找到名为 '{station_name}' 的车站")
            return
        
        # 构建回复消息
        reply = f"找到 {len(results)} 个匹配的车站：\n\n"
        reply = f"如果无线路，大概率为国铁车站\n"
        for station in results:
            if 'name' in station:
                reply += f"车站名称：{station['name']}\n"
            if 'city' in station:
                reply += f"城市：{station['city']}\n"
            if 'lines' in station:
                reply += f"接入线路：{'、'.join(station['lines'])}\n"
            if 'address' in station:
                reply += f"地址：{station['address']}\n"
            if 'description' in station:
                reply += f"简介：{station['description']}\n"
            reply += "\n"
        
        yield event.plain_result(reply.strip())
    
    @filter.command("station.add")
    async def add_station(self, event: AstrMessageEvent, *args):
        """
        添加新车站（管理员命令）
        用法: station.add {"name": "车站名", "city": "城市", "lines": ["线路1", "线路2"]}
        """
        # 检查权限
        if not event.is_admin():
            yield event.plain_result("权限不足，此命令仅管理员可用")
            return
        
        # 将所有参数拼接成完整的JSON字符串
        station_info = " ".join(args)
        
        if not station_info:
            yield event.plain_result("请输入车站信息，格式：station.add {\"name\": \"车站名\", \"city\": \"城市\", \"lines\": [\"线路1\", \"线路2\"]}")
            return
        
        try:
            # 解析车站信息
            station_data = json.loads(station_info)
            
            # 验证必要字段
            if not all(key in station_data for key in ["name", "city", "lines"]):
                yield event.plain_result("缺少必要字段，请确保包含 name、city 和 lines 字段")
                return
            
            # 生成车站ID
            new_id = f"station{len(self.stations_db['stations']) + 1:03d}"
            station_data["id"] = new_id
            
            # 添加到数据库
            self.stations_db["stations"].append(station_data)
            
            # 保存数据库
            if self._save_database():
                yield event.plain_result(f"车站 '{station_data['name']}' 添加成功！")
            else:
                yield event.plain_result("保存失败，请联系管理员")
                
        except json.JSONDecodeError:
            yield event.plain_result("JSON格式错误，请检查输入")
        except Exception as e:
            yield event.plain_result(f"添加失败: {str(e)}")
    
    @filter.command("station.list")
    async def list_stations(self, event: AstrMessageEvent):
        """
        列出所有车站
        用法: station.list
        """
        stations = self.stations_db.get("stations", [])
        
        if not stations:
            yield event.plain_result("数据库中暂无车站信息")
            return
        
        # 按城市分组
        cities = {}
        for station in stations:
            city = station.get("city", "未知")
            if city not in cities:
                cities[city] = []
            cities[city].append(station["name"])
        
        # 构建回复
        reply = "车站列表\n\n"
        for city, station_list in cities.items():
            reply += f"🏙️ **{city}**\n"
            reply += f"   {'、'.join(station_list)}\n\n"
        
        yield event.plain_result(reply.strip())
    
    @filter.command("station.help")
    async def station_help(self, event: AstrMessageEvent):
        """
        显示帮助信息
        用法: station.help
        """
        help_text = """
车站查询插件帮助

基础命令：
  - `station <车站名>` 或 `/station <车站名>` - 查询车站信息
  - `station.list` 或 `车站列表` - 列出所有车站
  - `station.help` 或 `车站帮助` - 显示此帮助

管理员命令：
  - `station.add {"name": "车站名", "city": "城市", "lines": ["线路1", "线路2"]}` - 添加新车站

使用示例：
  - `station 北京西站` - 查询北京西站的信息
  - `车站列表` - 查看所有车站
        """
        yield event.plain_result(help_text.strip())


# 插件入口
def main(context: Context) -> StationSearcherPlugin:
    return StationSearcherPlugin(context)