""" Change SafeConfigParser behavior to treat options without values as
    non-existent.
    将SafeConfigParser类修改，将空字段option视为不存在
"""
# 从ConfigParser导入SafeConfigParser，命名为OrigSafeConfigParser
#
# Python 标准库的 ConfigParser 模块提供一套 API 来读取和操作配置文件。

from ConfigParser import SafeConfigParser as OrigSafeConfigParser


# 从OrigSafeConfigParser派生SafeConfigParser类
class SafeConfigParser(OrigSafeConfigParser):
    # 定义方法，返回所有非空option组成的列表

    def items_with_value(self, section):
        finallist = []
        # .items()为父类方法，Return a list of (name, value) pairs for each option in the given section.
        items = self.items(section)
        for item in items:
            if item[1] != '':
                finallist.append(item)
        return finallist

    # 定义方法，判断option是否为非空字段
    def has_option_with_value(self, section, option):
        # has_option()为父类方法
        if self.has_option(section, option):
            # .get(section，option)为父类方法，Get an option value for the named section.
            if self.get(section, option) == '':
                return False
        else:
            return False
        return True
