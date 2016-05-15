"""Interface for registering map styles and layers for availability in WMS Requests."""

import re
import sys
import ConfigParser
from mapnik import Style, Map, load_map, load_map_from_string, Envelope, Coord

from ogcserver import common
from ogcserver.wms111 import ServiceHandler as ServiceHandler111
from ogcserver.wms130 import ServiceHandler as ServiceHandler130
from ogcserver.exceptions import OGCException, ServerConfigurationError

# ServiceHandlerFactory服务处理器参数
def ServiceHandlerFactory(conf, mapfactory, onlineresource, version):

    if not version:
        version = common.Version()
    else:
        version = common.Version(version)
    if version >= '1.3.0':
        return ServiceHandler130(conf, mapfactory, onlineresource)
    else:
        return ServiceHandler111(conf, mapfactory, onlineresource)

# named_rules 提取，输入为style类对象或list，输出为style对象
def extract_named_rules(s_obj):
    s = Style()
    s.names = []
    #判断s_obj是否为Style类型
    if isinstance(s_obj,Style):
        for rule in s_obj.rules:
            if rule.name:
                s.rules.append(rule)
                #对s.name列表中没有的name进行添加操作
                if not rule.name in s.names:
                    s.names.append(rule.name)
    #如果s_obj是list则按list的结构进行提取，效果与第一种相同
    elif isinstance(s_obj,list):
        for sty in s_obj:
            for rule in sty.rules:
                if rule.name:
                    s.rules.append(rule)
                    if not rule.name in s.names:
                        s.names.append(rule.name)
    #当提取数据不为空时，返回s
    if len(s.rules):
        return s
# 定义类BaseWMSFactory
# 
# 描述基本的wms参数
# 
# 待添加更具体描述

class BaseWMSFactory:
    def __init__(self, configpath=None):
        self.layers = {}
        self.ordered_layers = []
        self.styles = {}
        self.aggregatestyles = {}
        self.map_attributes = {}
        self.meta_styles = {}
        self.meta_layers = {}
        self.configpath = configpath
        self.latlonbb = None
    #定义方法：加载XML配置文件
    def loadXML(self, xmlfile=None, strict=False, xmlstring='', basepath=''):
        config = ConfigParser.SafeConfigParser()
        #声明变量，用于保存 map中的wms_srs
        map_wms_srs = None
        if self.configpath:
            config.readfp(open(self.configpath))

            if config.has_option('map', 'wms_srs'):
                map_wms_srs = config.get('map', 'wms_srs')
        #声明变量tmp_map保存Map(0,0),Map从mapnik模块中导入,此处详见doc/mapnik_help.text
        tmp_map = Map(0,0)
        #支持文件模式和字符串格式的输入
        if xmlfile:
            load_map(tmp_map, xmlfile, strict)
        elif xmlstring:
            load_map_from_string(tmp_map, xmlstring, strict, basepath)
        else:
            #差错机制
            raise ServerConfigurationError("Mapnik configuration XML is not specified - 'xmlfile' and 'xmlstring' variables are empty.\
Please set one of this variables to load mapnik map object.")
        # parse map level attributes
        #解析地图图层特征参数
        #背景颜色（待查）
        if tmp_map.background:
            self.map_attributes['bgcolor'] = tmp_map.background
        #buffer大小（待查）
        if tmp_map.buffer_size:
            self.map_attributes['buffer_size'] = tmp_map.buffer_size
        #对tmp_map中layers中所有lyr，进行参数解析
        for lyr in tmp_map.layers:
            layer_section = 'layer_%s' % lyr.name
            layer_wms_srs = None
            if config.has_option(layer_section, 'wms_srs'):
                layer_wms_srs = config.get(layer_section, 'wms_srs')
            else:
                layer_wms_srs = map_wms_srs

            if config.has_option(layer_section, 'title'):
                lyr.title = config.get(layer_section, 'title')
            else:
                lyr.title = ''

            if config.has_option(layer_section, 'abstract'):
                lyr.abstract = config.get(layer_section, 'abstract')
            else:
                lyr.abstract = ''

            style_count = len(lyr.styles)
            #必须设定有lyr.styles
            if style_count == 0:
                raise ServerConfigurationError("Cannot register Layer '%s' without a style" % lyr.name)
            elif style_count == 1:
                #.find_style方法为mapnik中Map类的方法？？？？？
                style_obj = tmp_map.find_style(lyr.styles[0])
                style_name = lyr.styles[0]
                # 对style_obj进行处理，提取参数返回为 style类
                meta_s = extract_named_rules(style_obj)
                if meta_s:
                    # BaseWMSFactory类的meta_styles属性
                    self.meta_styles['%s_meta' % lyr.name] = meta_s
                    # 判断lyr是否含有abstract属性
                    if hasattr(lyr,'abstract'):
                        name_ = lyr.abstract
                    else:
                        name_ = lyr.name
                    # 将meta_s.names中的字符串序列用“-”连接
                    meta_layer_name = '%s:%s' % (name_,'-'.join(meta_s.names))
                    # 将meta_layer_name中的空格全部替换为“_”
                    meta_layer_name = meta_layer_name.replace(' ','_')
                    self.meta_styles[meta_layer_name] = meta_s
                    meta_lyr = common.copy_layer(lyr)
                    meta_lyr.meta_style = meta_layer_name
                    meta_lyr.name = meta_layer_name
                    meta_lyr.wmsextrastyles = ()
                    meta_lyr.defaultstyle = meta_layer_name
                    meta_lyr.wms_srs = layer_wms_srs
                    self.ordered_layers.append(meta_lyr)
                    self.meta_layers[meta_layer_name] = meta_lyr
                    print meta_layer_name
                # 如果aggregatestyles和styles中没有style_name的关键字，则注册style。.register_style为本类定义的方法
                if style_name not in self.aggregatestyles.keys() and style_name not in self.styles.keys():
                    self.register_style(style_name, style_obj)

                # must copy layer here otherwise we'll segfault
                # c此处必须拷贝图层，否则将出现段错误
                # common
                lyr_ = common.copy_layer(lyr)
                lyr_.wms_srs = layer_wms_srs
                #register_layer为本类定义的一个方法，
                self.register_layer(lyr_, style_name, extrastyles=(style_name,))

            # 当style_count > 1时，处理步骤与style_count = 1时大致相同，
            elif style_count > 1:
                for style_name in lyr.styles:
                    style_obj = tmp_map.find_style(style_name)

                    meta_s = extract_named_rules(style_obj)
                    if meta_s:
                        self.meta_styles['%s_meta' % lyr.name] = meta_s
                        if hasattr(lyr,'abstract'):
                            name_ = lyr.abstract
                        else:
                            name_ = lyr.name
                        meta_layer_name = '%s:%s' % (name_,'-'.join(meta_s.names))
                        meta_layer_name = meta_layer_name.replace(' ','_')
                        self.meta_styles[meta_layer_name] = meta_s
                        meta_lyr = common.copy_layer(lyr)
                        meta_lyr.meta_style = meta_layer_name
                        print meta_layer_name
                        meta_lyr.name = meta_layer_name
                        meta_lyr.wmsextrastyles = ()
                        meta_lyr.defaultstyle = meta_layer_name
                        meta_lyr.wms_srs = layer_wms_srs
                        self.ordered_layers.append(meta_lyr)
                        self.meta_layers[meta_layer_name] = meta_lyr

                    if style_name not in self.aggregatestyles.keys() and style_name not in self.styles.keys():
                        self.register_style(style_name, style_obj)
                # 与style_count = 1时的不同之处，
                aggregates = tuple([sty for sty in lyr.styles])
                aggregates_name = '%s_aggregates' % lyr.name
                self.register_aggregate_style(aggregates_name,aggregates)
                # must copy layer here otherwise we'll segfault
                lyr_ = common.copy_layer(lyr)
                lyr_.wms_srs = layer_wms_srs
                self.register_layer(lyr_, aggregates_name, extrastyles=aggregates)
                if 'default' in aggregates:
                    sys.stderr.write("Warning: Multi-style layer '%s' contains a regular style named 'default'. \
This style will effectively be hidden by the 'all styles' default style for multi-style layers.\n" % lyr_.name)
#注册图层
    def register_layer(self, layer, defaultstyle, extrastyles=()):
        layername = layer.name
        #差错机制，检测相关参数是否有效
        if not layername:
            #ServerConfigurationError为从ogcserver.exceptions中导入的方法，执行内容为空
            raise ServerConfigurationError('Attempted to register an unnamed layer.')
        if not layer.wms_srs and not re.match('^\+init=epsg:\d+$', layer.srs) and not re.match('^\+proj=.*$', layer.srs):
            raise ServerConfigurationError('Attempted to register a layer without an epsg projection defined.')
        if defaultstyle not in self.styles.keys() + self.aggregatestyles.keys():
            raise ServerConfigurationError('Attempted to register a layer with an non-existent default style.')
        layer.wmsdefaultstyle = defaultstyle
        # 判断是否为tuple类型，（'a',)为tuple类型，aggregates也为tuple类型
        # type(('a',))输出为 tuple
        if isinstance(extrastyles, tuple):
            # 
            for stylename in extrastyles:
                # 如果stylename类型为str
                if type(stylename) == type(''):
                    if stylename not in self.styles.keys() + self.aggregatestyles.keys():
                        raise ServerConfigurationError('Attempted to register a layer with an non-existent extra style.')
                else:
                    ServerConfigurationError('Attempted to register a layer with an invalid extra style name.')
            # wmsextrastyles？？？？
            layer.wmsextrastyles = extrastyles
        else:
            raise ServerConfigurationError('Layer "%s" was passed an invalid list of extra styles.  List must be a tuple of strings.' % layername)
        # 调用common中Projection
        layerproj = common.Projection(layer.srs)
        env = layer.envelope()
        llp = layerproj.inverse(Coord(env.minx, env.miny))
        urp = layerproj.inverse(Coord(env.maxx, env.maxy))
        if self.latlonbb is None:
            self.latlonbb = Envelope(llp, urp)
        else:
            self.latlonbb.expand_to_include(Envelope(llp, urp))
        self.ordered_layers.append(layer)
        self.layers[layername] = layer

# 注册style
    def register_style(self, name, style):
        # 差错处理，是否输入name，name是否已经存在，style类型是否正确
        if not name:
            raise ServerConfigurationError('Attempted to register a style without providing a name.')
        if name in self.aggregatestyles.keys() or name in self.styles.keys():
            raise ServerConfigurationError("Attempted to register a style with a name already in use: '%s'" % name)
        if not isinstance(style, Style):
            raise ServerConfigurationError('Bad style object passed to register_style() for style "%s".' % name)
        # 在对象的style属性的dict中添加style
        self.styles[name] = style

# 注册aggregatestyles
    def register_aggregate_style(self, name, stylenames):
        if not name:
            raise ServerConfigurationError('Attempted to register an aggregate style without providing a name.')
        if name in self.aggregatestyles.keys() or name in self.styles.keys():
            raise ServerConfigurationError('Attempted to register an aggregate style with a name already in use.')
        self.aggregatestyles[name] = []
        for stylename in stylenames:
            if stylename not in self.styles.keys():
                raise ServerConfigurationError('Attempted to register an aggregate style containing a style that does not exist.')
            # 在对象的aggregatestyles属性的dict中添加name关键字，及其内容
            self.aggregatestyles[name].append(stylename)

    def finalize(self):
        if len(self.layers) == 0:
            raise ServerConfigurationError('No layers defined!')
        if len(self.styles) == 0:
            raise ServerConfigurationError('No styles defined!')
        for layer in self.layers.values():
            for style in list(layer.styles) + list(layer.wmsextrastyles):
                if style not in self.styles.keys() + self.aggregatestyles.keys():
                    raise ServerConfigurationError('Layer "%s" refers to undefined style "%s".' % (layer.name, style))
