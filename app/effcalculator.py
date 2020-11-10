import json
import os
from copy import deepcopy

import PySimpleGUI as sg
import matplotlib
import numpy as np
import unyt

matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as FigureCanvas
import matplotlib.pyplot as plt

from cavag.utils import calculate_total_efficiency

# from random import choice

# sg.theme(choice(sg.theme_list()))

class Config(object):
    def __init__(self, filename):
        self._filename = filename
        with open(filename, encoding='utf-8') as fp:
            self.__dict__.update(json.load(fp))

    def dump(self):
        with open(self._filename, 'w', encoding='utf-8') as fp:
            data = {}
            for key in self.__dict__:
                if not key.startswith('_'):
                    data[key] = self.__dict__[key]
            json.dump(data, fp, ensure_ascii=False, indent=2)


# 导入数据
LOCAL_DIRNAME = os.path.abspath(os.path.dirname(__file__))
DATASET = Config(os.path.join(LOCAL_DIRNAME, "dataset.json"))
CONFIGURATION = Config(os.path.join(LOCAL_DIRNAME, "configuration.json"))

changeable_properties = []
for key in dir(DATASET):
    if not key.startswith('_'):
        try:
            if getattr(DATASET, key)['changeable']:
                changeable_properties.append(key)
        except:
            pass

def handle_roundoff(value):
    return float("%.10g" % value)


def convert_value_with_unit(value, srcunit, destunit):
    unit = getattr(unyt, srcunit)
    _v = value * unit
    _v = _v.to(destunit)
    return _v.value


def value_with_unit(prop, show_unit=None):
    data = getattr(DATASET, prop)

    value = data['default']
    unit = data['unit']
    if not show_unit:
        show_unit = data['show_unit']
    if unit:
        value = convert_value_with_unit(value, unit, show_unit)
    return value, show_unit


def show_value_with_unit(value_unit):
    value, unit = value_unit
    if not unit:
        return "%g" % value
    else:
        return "%g(%s)" % (value, unit)


# 计算效率所用的布置
compute_layout = []
# 绘制效率所用的布置
plot_layout = []

# Lookup dictionary that maps the events to functions to call
dispatch_dict = {}

# 所有的Key，便于查询
key_prob = '-PROB-'
key_prob_compute = '-PROB-COMPUTE-'

key_fiber = "-FIBER_SELECTED-"
key_fiber_info = "-FIBER_SELECTED-INFO-"

key_fiber_add = "-FIBER-ADD-"
key_fiber_remove = "-FIBER-REMOVE-"

key_prop_table = {}

key_prop_select = '-PROP-SELECT-'
key_prop_select_info = '-PROP-SELECT-INFO-'
key_prop_select_min = '-PROP-SELECT-MIN-'
key_prop_select_step = '-PROP-SELECT-STEP-'
key_prop_select_max = '-PROP-SELECT-MAX-'
key_prop_select_set = '-PROP-SELECT-SET-'
key_prop_select_show_unit = '-PROP-SELECT-SHOW-UNIT-'

key_prop_plot = '-PROP-PLOT-'
key_prop_plot_canvas = '-PROP-PLOT-CANVAS-'
key_prop_plot_save = '-PROP-PLOT-SAVE-'


# 函数用于获得计算效率所用参数表
def get_params_table():
    table = {}
    for prop in changeable_properties:
        table[prop] = getattr(DATASET, prop)['default']
    table['gamma'] = getattr(DATASET, 'gamma')['default']
    table['wavelength'] = getattr(DATASET, 'wavelength')['default']
    table['fiber'] = DATASET.fiber['types'][DATASET.fiber['default']]

    return table


# 函数用于计算效率
def compute_prob(table):

    prob = -1
    try:
        prob = calculate_total_efficiency(L=table['L'],
                                          surL=(table['ROCl'], table['D'], table['Rl'], table['T2L'], table['sigmasc']),
                                          fiberL=(table['fiber']['nf'], table['fiber']['omegaf']),
                                          surR=(table['ROCr'], table['D'], table['Rr'], table['T2L'], table['sigmasc']),
                                          fiberR=(table['fiber']['nf'], table['fiber']['omegaf']),
                                          wavelength=table['wavelength'],
                                          gamma=table['gamma'],
                                          direction='l')
    except Exception as e:
        print(str(e))

    return prob


# 函数用于计算效率与某个变量关系
def compute_prob_var(prop, n=300):
    table = get_params_table()

    data = getattr(DATASET, prop)
    min = data['min']
    step = data['step']
    max = data['max']
    if min > max:
        raise ValueError('最大值必须比最小值大')
    if max == float('inf'):
        n = int(n)
        x = np.arange(n) * step + min
    else:
        n = np.min([int(n), np.max([int((max - min) / step), 50])])
        x = np.linspace(min, max, n)

    y = np.empty_like(x)

    for ind in range(len(x)):
        table[prop] = x[ind]
        y[ind] = compute_prob(table)

    validInd = (y > 0) & (np.isreal(y))

    if not validInd.any():
        raise ValueError('请选择合适的区间范围')

    return x[validInd], y[validInd]


try:
    # 计算效率和绘制相关参数界面
    ly_prob = [[sg.Text('计算%s在光纤腔中发射%s光子的效率' % (DATASET.description['particle'], show_value_with_unit(value_with_unit('wavelength'))))],
               [sg.Text('单个光子获取的概率:'), sg.Text(size=(8, 1), key=key_prob),
                sg.Button('计算', key=key_prob_compute)],
               [sg.Text('_' * 70)]]
    compute_layout.extend(ly_prob)


    def update_prob(event):
        if event == key_prob_compute:
            prob = compute_prob(get_params_table())
            window[key_prob].update(str(prob))


    dispatch_dict[key_prob_compute] = update_prob

    # 光纤选择框界面
    ly_fiber = [
        [sg.Text("选择所需的光纤:")],
        [
            sg.Text("光纤:"),
            sg.InputCombo(tuple(DATASET.fiber['types'].keys()),
                          default_value=DATASET.fiber['default'], size=(8, 1),
                          enable_events=True, key=key_fiber),
            sg.Text("参数:"),
            sg.Text(str(DATASET.fiber['types'][DATASET.fiber['default']]),
                    size=(40, 1), key=key_fiber_info)
        ]
    ]
    compute_layout.extend(ly_fiber)


    def update_fiber(event):
        if event == key_fiber:
            DATASET.fiber['default'] = values[event]
            window[key_fiber_info].update(str(DATASET.fiber['types'][values[event]]))


    dispatch_dict[key_fiber] = update_fiber

    # 添加和删除光纤种类界面
    ly_fiber_add = [[sg.Text('type:'), sg.InputText('', size=(6, 1)),
                     sg.Text('nf:'), sg.InputText('', size=(6, 1)),
                     sg.Text('omegaf:'), sg.InputText('', size=(6, 1)),
                     sg.Button("添加", key=key_fiber_add)]]
    ly_fiber_remove = [[sg.InputCombo(tuple(DATASET.fiber['types'].keys()), size=(6, 1)),
                        sg.Button("删除", key=key_fiber_remove)]]
    ly_fiber_addremove = [
        [sg.Text("添加或删除光纤:")],
        [sg.Frame(title="添加光纤", layout=ly_fiber_add),
         sg.Frame(title="删除光纤", layout=ly_fiber_remove)
         ],
        [sg.Text('_' * 70)]
    ]
    compute_layout.extend(ly_fiber_addremove)


    def update_fiber_addremove(event):
        if event == key_fiber_add:
            try:
                type = str(ly_fiber_add[0][1].get())
                nf = float(ly_fiber_add[0][3].get())
                omegaf = float(ly_fiber_add[0][5].get())
            except ValueError as e:
                print(str(e))
                return
            DATASET.fiber['types'][type] = {
                'type': type, 'nf': nf, 'omegaf': omegaf
            }
        elif event == key_fiber_remove:
            type = ly_fiber_remove[0][0].get()
            try:
                del DATASET.fiber['types'][type]
            except Exception as e:
                print(str(e))
        window[key_fiber].update(value='', values=tuple(DATASET.fiber['types'].keys()))
        window[key_fiber_info].update('')
        ly_fiber_remove[0][0].update(value='', values=tuple(DATASET.fiber['types'].keys()))


    dispatch_dict[key_fiber_add] = update_fiber_addremove
    dispatch_dict[key_fiber_remove] = update_fiber_addremove


    # 光纤腔属性界面
    def update_prop(event):
        p = event.split('-')[1]
        for prop in changeable_properties:
            if prop.upper() == p:
                break
        else:
            return
        try:
            value = float(window[event.replace('CHANGE', 'INPUT')].get())
            show_unit = window[event.replace('CHANGE', 'SHOW-UNIT')].get()
        except Exception as e:
            print(str(e))
            return
        getattr(DATASET, prop)['default'] = handle_roundoff(
            convert_value_with_unit(value, show_unit, getattr(DATASET, prop)['unit']))
        getattr(DATASET, prop)['show_unit'] = show_unit
        window[event.replace('CHANGE', 'VALUE')].update(show_value_with_unit(value_with_unit(prop)))


    for prop in changeable_properties:
        prop_info = getattr(DATASET, prop)['info']
        prop_value, prop_show_unit = value_with_unit(prop)

        key_prop_change = '-' + prop.upper() + '-CHANGE-'
        key_prop_value = '-' + prop.upper() + '-VALUE-'
        key_prop_input = '-' + prop.upper() + '-INPUT-'
        key_prop_show_unit = '-' + prop.upper() + '-SHOW-UNIT-'
        key_prop_table[prop] = {'key_prop_change': key_prop_change,
                                'key_prop_value': key_prop_value,
                                'key_prop_input': key_prop_input,
                                'key_prop_show_unit': key_prop_show_unit}

        ly_prop = [[sg.Text('%s(%s):' % (prop_info, prop), size=(20, 1)),
                    sg.Text('数值:'),
                    sg.Text(show_value_with_unit(value_with_unit(prop)), size=(10, 1), key=key_prop_value),
                    sg.Input(str(handle_roundoff(prop_value)), size=(10, 1), key=key_prop_input),
                    sg.Text(prop_show_unit, size=(2, 1), key=key_prop_show_unit),
                    sg.Button('设置', key=key_prop_change)]]
        compute_layout.extend(ly_prop)
        dispatch_dict[key_prop_change] = update_prop

    # 选择属性界面
    ly_prop_select_frame = [
        [sg.Text('属性参数:'), sg.InputCombo(changeable_properties, size=(7, 1), key=key_prop_select, enable_events=True),
         sg.Text('参数:'), sg.Text(size=(55, 1), key=key_prop_select_info)],
        [sg.Text("最小值:"), sg.Input(size=(10, 1), key=key_prop_select_min),
         sg.Text("步长:"), sg.Input(size=(10, 1), key=key_prop_select_step),
         sg.Text("最大值:"), sg.Input(size=(10, 1), key=key_prop_select_max),
         sg.Text("单位："), sg.Text("", size=(2, 1), key=key_prop_select_show_unit),
         sg.Button('设置', key=key_prop_select_set)]
    ]

    ly_prop_select = [[sg.Frame("选择属性", ly_prop_select_frame)],
                      [sg.Text('_' * 95)]]
    plot_layout.extend(ly_prop_select)


    def update_prop_select(event):
        prop = window[key_prop_select].get()

        if prop not in changeable_properties:
            return

        _show_info_of = ('min','step','max','unit','show_unit')

        if event == key_prop_select:
            data = {k:v for k, v in getattr(DATASET, prop).items() if k in _show_info_of}
            unit = data['unit']
            show_unit = data['show_unit']

            window[key_prop_select_min].update(
                str(handle_roundoff(convert_value_with_unit(data['min'], unit, show_unit))))
            window[key_prop_select_step].update(
                str(handle_roundoff(convert_value_with_unit(data['step'], unit, show_unit))))
            window[key_prop_select_max].update(
                str(handle_roundoff(convert_value_with_unit(data['max'], unit, show_unit))))
            window[key_prop_select_show_unit].update(str(data['show_unit']))
        elif event == key_prop_select_set:
            data = getattr(DATASET, prop)
            unit = data['unit']
            show_unit = data['show_unit']
            try:
                min = convert_value_with_unit(float(window[key_prop_select_min].get()), show_unit, unit)
                step = convert_value_with_unit(float(window[key_prop_select_step].get()), show_unit, unit)
                max = convert_value_with_unit(float(window[key_prop_select_max].get()), show_unit, unit)
            except Exception as e:
                print(e)
                return
            data['min'] = handle_roundoff(min)
            data['step'] = handle_roundoff(step)
            data['max'] = handle_roundoff(max)

            data = {k:v for k, v in getattr(DATASET, prop).items() if k in _show_info_of}

        window[key_prop_select_info].update(str(data))


    dispatch_dict[key_prop_select] = update_prop_select
    dispatch_dict[key_prop_select_set] = update_prop_select

    # 绘制对应属性的效率图
    prop_plot_fig, prop_plot_ax = plt.subplots(1, 1)
    prop_plot_ax.axis('off')
    prop_plot_fig.subplots_adjust(top=0.92, bottom=0.08, left=0.10, right=0.95, hspace=0.25,
                                  wspace=0.35)
    _, _, prop_plot_fig_w, prop_plot_fig_h = prop_plot_fig.bbox.bounds


    def draw_figure(canvas, figure):
        figure_canvas_agg = FigureCanvas(figure, canvas)
        figure_canvas_agg.draw()
        figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
        return figure_canvas_agg


    ly_prop_plot = [[sg.Text("绘制光子发射效率相关曲线"),
                     sg.Button('绘制', key=key_prop_plot), sg.Button('保存', key=key_prop_plot_save)],
                    [sg.Canvas(size=(prop_plot_fig_w, prop_plot_fig_h), key=key_prop_plot_canvas)]]
    plot_layout.extend(ly_prop_plot)


    def update_prop_plot(event):
        if event == key_prop_plot:
            prop = window[key_prop_select].get()
            if prop not in changeable_properties:
                return
            print('计算属性%s - %s' % (prop, window[key_prop_select_info].get()))
            try:
                _x, _y = compute_prob_var(prop)
                _prob = compute_prob(get_params_table())  # 当前参数组下的效率
                # scale the value to some unit
                _unit = getattr(DATASET, prop)['unit']
                _show_unit = getattr(DATASET, prop)['show_unit']
                _x = convert_value_with_unit(_x, _unit, _show_unit)
                _y *= 100
                _prob *= 100
            except ValueError as e:
                print(e)
                return
            _table = get_params_table()
            table = {k: show_value_with_unit(value_with_unit(k)) for k in changeable_properties}
            _value = table.pop(prop)
            table['fiber'] = _table['fiber']['type']

            prop_plot_ax.cla()
            prop_plot_ax.set_ylim(0, 100)
            prop_plot_ax.plot(_x, _y)
            prop_plot_ax.hlines([_prob], _x[0], _x[-1], colors='k', linestyles='dashed')
            prop_plot_ax.text((_x[0] + _x[-1]) / 2, _prob, '给定参数%s=%s，效率%g%%' % (prop, _value, _prob),
                              horizontalalignment='center',
                              verticalalignment='bottom')
            prop_plot_ax.vlines([_x[0], _x[-1]], 0, np.max([_y[0], _y[-1]]), colors='r', linestyles='dashed')
            prop_plot_ax.table(cellText=[[k, v] for k, v in table.items()],
                               loc='best',
                               colWidths=[0.15, 0.15])
            prop_plot_ax.grid()
            prop_plot_ax.set_title(
                "%s的%s单光子发射效率随%s影响" % (DATASET.description['particle'],
                    show_value_with_unit(value_with_unit('wavelength')), getattr(DATASET, prop)['info']))
            prop_plot_ax.set_ylabel('efficiency(%)')
            _xlabel = '%s(%s)' % (prop, _show_unit) if _show_unit else prop
            prop_plot_ax.set_xlabel(_xlabel)
            prop_plot_canvas_agg.draw()
        elif event == key_prop_plot_save:
            if os.path.isdir(CONFIGURATION.initial_folder):
                _initial_folder = CONFIGURATION.initial_folder
            else:
                _initial_folder = os.getcwd()
            _filename = sg.popup_get_file('输入保存的文件名:',
                                          save_as=True, file_types=(('png格式图像', '*.png'), ('svg矢量图', '*.svg')),
                                          keep_on_top=True, initial_folder=_initial_folder, no_window=True)
            if os.path.split(_filename)[-1].split('.')[0]:
                CONFIGURATION.initial_folder = os.path.dirname(_filename)
                prop_plot_fig.savefig(_filename)
                print('保存图片至', _filename)


    dispatch_dict[key_prop_plot] = update_prop_plot
    dispatch_dict[key_prop_plot_save] = update_prop_plot

    # 标准输出
    compute_layout.extend([[sg.Output(size=(70, 8))]])

    # 主界面布置
    main_layout = [[sg.Frame("", compute_layout),
                    sg.Frame("", plot_layout)]
                   ]

    window = sg.Window('光纤腔光子效率计算工具', main_layout, return_keyboard_events=True, finalize=True)

    # add the plot to the window
    prop_plot_canvas_agg = draw_figure(window[key_prop_plot_canvas].TKCanvas, prop_plot_fig)

    while True:
        event, values = window.read()
        if event in (None, 'Exit', 'Escape:27'):
            break
        if event in dispatch_dict:
            func = dispatch_dict[event]
            func(event)

    window.close()
finally:
    # 导出数据
    DATASET.dump()
    CONFIGURATION.dump()

