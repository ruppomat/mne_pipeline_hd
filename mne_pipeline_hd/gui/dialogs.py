# -*- coding: utf-8 -*-
"""
Pipeline-GUI for Analysis with MNE-Python
@author: Martin Schulz
@email: dev@earthman-music.de
@github: https://github.com/marsipu/mne_pipeline_hd
License: BSD (3-clause)
Written on top of MNE-Python
Copyright © 2011-2020, authors of MNE-Python (https://doi.org/10.3389/fnins.2013.00267)
inspired by Andersen, L. M. (2018) (https://doi.org/10.3389/fnins.2018.00006)
"""
import shutil
import smtplib
import ssl
import sys
from ast import literal_eval
from collections import Counter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial
from os.path import join
from pathlib import Path

import mne
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox, QDialog, QDockWidget, QGridLayout, QHBoxLayout,
                             QInputDialog,
                             QLabel, QLineEdit, QListView, QMessageBox, QPushButton,
                             QScrollArea, QSizePolicy, QStyle, QTabWidget, QTextEdit, QVBoxLayout, QWidget)
from mne_pipeline_hd.gui import parameter_widgets
from mne_pipeline_hd.gui.base_widgets import CheckList, SimpleList
from mne_pipeline_hd.gui.gui_utils import WorkerDialog, set_ratio_geometry
from mne_pipeline_hd.gui.models import CheckListModel
from mne_pipeline_hd.gui.parameter_widgets import BoolGui, StringGui
from mne_pipeline_hd.pipeline_functions import iswin
from mne_pipeline_hd.pipeline_functions.loading import MEEG
from mne_pipeline_hd.pipeline_functions.project import Project


class CheckListDlg(QDialog):
    def __init__(self, parent, data, checked):
        """
        BaseClass for A Dialog with a Check-List, open() has to be called in SubClass or directly
        :param parent: parent-Widget
        :param data: Data for the Check-List
        :param checked: List, where Checked Data-Items are stored
        """
        super().__init__(parent)
        self.data = data
        self.checked = checked

        self.init_ui()

    def init_ui(self):
        self.layout = QGridLayout()

        self.lv = QListView()
        self.lm = CheckListModel(self.data, self.checked)
        self.lv.setModel(self.lm)
        self.layout.addWidget(self.lv, 0, 0, 1, 2)

        self.do_bt = QPushButton('<Do Something>')
        self.do_bt.clicked.connect(lambda: None)
        self.layout.addWidget(self.do_bt, 1, 0)

        self.quit_bt = QPushButton('Quit')
        self.quit_bt.clicked.connect(self.close)
        self.layout.addWidget(self.quit_bt, 1, 1)

        self.setLayout(self.layout)


class RemovePPresetDlg(CheckListDlg):
    def __init__(self, parent):
        self.parent = parent
        self.preset_list = [p for p in self.parent.mw.pr.parameters if p != 'Default']
        self.rm_list = []

        super().__init__(parent, self.preset_list, self.rm_list)

        self.do_bt.setText('Remove Parameter-Preset')
        self.do_bt.clicked.connect(self.remove_selected)

        self.open()

    def remove_selected(self):
        for p_preset in self.rm_list:
            self.preset_list.remove(p_preset)
            self.lm.layoutChanged.emit()
            # Remove from Parameters
            self.parent.mw.pr.parameters.pop(p_preset)
            self.parent.update_ppreset_cmbx()

        # If current Parameter-Preset was deleted
        if self.parent.mw.pr.p_preset not in self.parent.mw.pr.parameters:
            self.parent.mw.pr.p_preset = list(self.parent.mw.pr.parameters.keys())[0]
            self.parent.update_all_param_guis()

        self.close()


class RemoveProjectsDlg(CheckListDlg):
    def __init__(self, main_win, controller):
        self.mw = main_win
        self.ct = controller
        self.rm_list = []
        super().__init__(main_win, self.ct.projects, self.rm_list)

        self.do_bt.setText('Remove Projects')
        self.do_bt.clicked.connect(self.remove_selected)

        self.open()

    def remove_selected(self):
        for project in self.rm_list:
            self.ct.projects.remove(project)
            self.lm.layoutChanged.emit()

            # Remove Project-Folder
            try:
                shutil.rmtree(join(self.ct.projects_path, project))
            except OSError:
                QMessageBox.critical(self, 'Deletion impossible',
                                     f'The folder of {project} can\'t be deleted and has to be deleted manually')

        # If current project was deleted, load remaining or create New
        if self.ct.current_project not in self.ct.projects:
            if len(self.ct.projects) != 0:
                self.ct.current_project = self.ct.projects[0]
            else:
                self.ct.current_project = 'Dummy'
            self.ct.pr = Project(self.ct, self.ct.current_project)
            self.mw.project_updated()
        else:
            self.mw.update_project_box()

        self.close()


class SettingsDlg(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

        self.init_ui()
        self.open()

    def init_ui(self):
        layout = QVBoxLayout()

        # layout.addWidget(IntGui(self.mw.qsettings, 'n_jobs', min_val=-1, special_value_text='Auto',
        #                         description='Set to the amount of cores of your machine '
        #                              'you want to use for multiprocessing', default=-1))
        # layout.addWidget(BoolGui(self.mw.settings, 'show_plots', param_alias='Show Plots',
        #                          description='Do you want to show plots?\n'
        #                               '(or just save them without showing, then just check "Save Plots")',
        #                          default=True))
        # layout.addWidget(BoolGui(self.mw.settings, 'save_plots', param_alias='Save Plots',
        #                          description='Do you want to save the plots made to a file?', default=True))
        # layout.addWidget(BoolGui(QSettings(), 'enable_cuda', param_alias='Enable CUDA',
        #                          description='Do you want to enable CUDA? (system has to be setup for cuda)',
        #                          default=False))
        # layout.addWidget(BoolGui(self.mw.settings, 'shutdown', param_alias='Shutdown',
        #                          description='Do you want to shut your system down after execution of all subjects?'))
        # layout.addWidget(IntGui(self.mw.settings, 'dpi', min_val=0, max_val=10000,
        #                         description='Set dpi for saved plots', default=300))
        # layout.addWidget(ComboGui(self.mw.settings, 'img_format', self.mw.available_image_formats,
        #                           param_alias='Image-Format', description='Choose the image format for plots',
        #                           default='.png'))

        layout.addWidget(BoolGui(self.mw.qsettings, 'save_ram', param_alias='Save RAM',
                                 description='Set to True on low RAM-Machines to avoid the process to be killed '
                                             'by the OS due to low Memory (with leaving it off, the pipeline goes'
                                             'a bit faster, because the data can be saved in memory)', default=True))

        layout.addWidget(StringGui(self.mw.qsettings, 'fs_path', param_alias='FREESURFER_HOME-Path',
                                   description='Set the Path to the "freesurfer"-directory of your '
                                               'Freesurfer-Installation '
                                               '(for Windows to the LINUX-Path of the Freesurfer-Installation '
                                               'in Windows-Subsystem for Linux(WSL))',
                                   default=None, none_select=True))
        if iswin:
            layout.addWidget(StringGui(self.mw.qsettings, 'mne_path', param_alias='MNE-Python-Path',
                                       description='Set the LINUX-Path to the mne-environment (e.g '
                                                   '...anaconda3/envs/mne) '
                                                   'in Windows-Subsystem for Linux(WSL))',
                                       default=None, none_select=True))

        close_bt = QPushButton('Close')
        close_bt.clicked.connect(self.close)
        layout.addWidget(close_bt)

        self.setLayout(layout)


# Todo: Ordering Parameters in Tabs and add Find-Command
class ResetDialog(QDialog):
    def __init__(self, p_dock):
        super().__init__(p_dock)
        self.pd = p_dock
        self.selected_params = list()

        self.init_ui()
        self.open()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(CheckList(list(self.pd.mw.pr.parameters[self.pd.mw.pr.p_preset].keys()),
                                   self.selected_params,
                                   title='Select the Parameters to reset'))
        reset_bt = QPushButton('Reset')
        reset_bt.clicked.connect(self.reset_params)
        layout.addWidget(reset_bt)

        close_bt = QPushButton('Close')
        close_bt.clicked.connect(self.close)
        layout.addWidget(close_bt)

        self.setLayout(layout)

    def reset_params(self):
        for param_name in self.selected_params:
            self.pd.mw.pr.load_default_param(param_name)
            print(f'Reset {param_name}')
        WorkerDialog(self, self.pd.mw.pr.save, title='Saving project...', blocking=True)
        self.pd.update_all_param_guis()
        self.close()


class CopyPDialog(QDialog):
    def __init__(self, p_dock):
        super().__init__(p_dock)
        self.pd = p_dock
        self.p = p_dock.mw.pr.parameters
        self.selected_from = None
        self.selected_to = list()
        self.selected_ps = list()

        self.init_ui()
        self.open()

    def init_ui(self):
        layout = QVBoxLayout()

        list_layout = QHBoxLayout()
        copy_from = SimpleList(list(self.p.keys()))
        copy_from.currentChanged.connect(self.from_selected)
        list_layout.addWidget(copy_from)

        self.copy_to = CheckList(checked=self.selected_to)
        list_layout.addWidget(self.copy_to)

        self.copy_ps = CheckList(checked=self.selected_ps)
        list_layout.addWidget(self.copy_ps)

        layout.addLayout(list_layout)

        bt_layout = QHBoxLayout()

        copy_bt = QPushButton('Copy')
        copy_bt.clicked.connect(self.copy_parameters)
        bt_layout.addWidget(copy_bt)

        close_bt = QPushButton('Close')
        close_bt.clicked.connect(self.close)
        bt_layout.addWidget(close_bt)

        layout.addLayout(bt_layout)

        self.setLayout(layout)

    def from_selected(self, current):
        self.selected_from = current
        self.copy_to.replace_data([pp for pp in self.p.keys() if pp != current])
        self.copy_ps.replace_data([p for p in self.p[current]])

    def copy_parameters(self):
        if len(self.selected_to) > 0:
            for p_preset in self.selected_to:
                for parameter in self.selected_ps:
                    self.p[p_preset][parameter] = self.p[self.selected_from][parameter]

            WorkerDialog(self, self.pd.mw.pr.save, title='Saving project...', blocking=True)
            self.pd.update_all_param_guis()
            self.close()


class ParametersDock(QDockWidget):
    def __init__(self, main_win):
        super().__init__('Parameters', main_win)
        self.mw = main_win
        self.setAllowedAreas(Qt.RightDockWidgetArea)
        self.main_widget = QWidget()
        self.param_guis = {}

        self.dropgroup_params()
        self.init_ui()

    def dropgroup_params(self):
        # Create a set of all unique parameters used by functions in selected_modules
        sel_pdfuncs = self.mw.pd_funcs.loc[self.mw.pd_funcs['module'].isin(self.mw.get_setting('selected_modules'))]
        # Remove rows with NaN in func_args
        sel_pdfuncs = sel_pdfuncs.loc[sel_pdfuncs['func_args'].notna()]
        all_used_params_str = ','.join(sel_pdfuncs['func_args'])
        # Make sure there are no spaces left
        all_used_params_str = all_used_params_str.replace(' ', '')
        all_used_params = set(all_used_params_str.split(','))
        drop_idx_list = list()
        self.cleaned_pd_params = self.mw.pd_params.copy()
        for param in self.cleaned_pd_params.index:
            if param in all_used_params:
                # Group-Name (if not given, set to 'Various')
                group_name = self.cleaned_pd_params.loc[param, 'group']
                if pd.isna(group_name):
                    self.cleaned_pd_params.loc[param, 'group'] = 'Various'
            else:
                # Drop Parameters which aren't used by functions
                drop_idx_list.append(param)
        self.cleaned_pd_params.drop(index=drop_idx_list, inplace=True)

    def init_ui(self):
        self.general_layout = QVBoxLayout()

        # Add Parameter-Preset-ComboBox
        title_layouts = QVBoxLayout()
        title_layout1 = QHBoxLayout()
        p_preset_l = QLabel('Parameter-Presets: ')
        title_layout1.addWidget(p_preset_l)
        self.p_preset_cmbx = QComboBox()
        self.p_preset_cmbx.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.p_preset_cmbx.activated.connect(self.p_preset_changed)
        self.update_ppreset_cmbx()
        title_layout1.addWidget(self.p_preset_cmbx)

        add_bt = QPushButton(icon=self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        add_bt.clicked.connect(self.add_p_preset)
        title_layout1.addWidget(add_bt)

        rm_bt = QPushButton(icon=self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        rm_bt.clicked.connect(partial(RemovePPresetDlg, self))
        title_layout1.addWidget(rm_bt)

        title_layouts.addLayout(title_layout1)

        title_layout2 = QHBoxLayout()
        copy_bt = QPushButton('Copy')
        copy_bt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        copy_bt.clicked.connect(partial(CopyPDialog, self))
        title_layout2.addWidget(copy_bt)

        reset_bt = QPushButton('Reset')
        reset_bt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        reset_bt.clicked.connect(partial(ResetDialog, self))
        title_layout2.addWidget(reset_bt)

        reset_all_bt = QPushButton('Reset All')
        reset_all_bt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        reset_all_bt.clicked.connect(self.reset_all_parameters)
        title_layout2.addWidget(reset_all_bt)

        title_layouts.addLayout(title_layout2)
        self.general_layout.addLayout(title_layouts)

        self.add_param_guis()

        self.main_widget.setLayout(self.general_layout)
        self.setWidget(self.main_widget)

    def add_param_guis(self):
        # Create Tab-Widget for Parameters, grouped by group
        self.tab_param_widget = QTabWidget()

        grouped_params = self.cleaned_pd_params.groupby('group', sort=False)

        for group_name, group in grouped_params:
            layout = QVBoxLayout()
            tab = QScrollArea()
            child_w = QWidget()
            for idx, parameter in group.iterrows():

                # Get Parameters for Gui-Call
                if pd.notna(parameter['alias']):
                    param_alias = parameter['alias']
                else:
                    param_alias = idx
                if pd.notna(parameter['gui_type']):
                    gui_name = parameter['gui_type']
                else:
                    gui_name = 'FuncGui'
                try:
                    default = literal_eval(parameter['default'])
                except (SyntaxError, ValueError):
                    if gui_name == 'FuncGui':
                        default = eval(parameter['default'], {'np': np})
                    else:
                        default = parameter['default']
                if pd.notna(parameter['description']):
                    description = parameter['description']
                else:
                    description = ''
                if pd.notna(parameter['unit']):
                    unit = parameter['unit']
                else:
                    unit = None
                try:
                    gui_args = literal_eval(parameter['gui_args'])
                except (SyntaxError, ValueError):
                    gui_args = {}

                gui_handle = getattr(parameter_widgets, gui_name)
                self.param_guis[idx] = gui_handle(self.mw, param_name=idx, param_alias=param_alias,
                                                  default=default, description=description, param_unit=unit, **gui_args)

                layout.addWidget(self.param_guis[idx])

            child_w.setLayout(layout)
            tab.setWidget(child_w)
            self.tab_param_widget.addTab(tab, group_name)

        # Set Layout of QWidget (the class itself)
        self.general_layout.addWidget(self.tab_param_widget)

    def update_ppreset_cmbx(self):
        self.p_preset_cmbx.clear()
        for p_preset in self.mw.pr.parameters.keys():
            self.p_preset_cmbx.addItem(p_preset)
        if self.mw.pr.p_preset in self.mw.pr.parameters.keys():
            self.p_preset_cmbx.setCurrentText(self.mw.pr.p_preset)
        else:
            self.p_preset_cmbx.setCurrentText(list(self.mw.pr.parameters.keys())[0])

    def p_preset_changed(self, idx):
        self.mw.pr.p_preset = self.p_preset_cmbx.itemText(idx)
        self.update_all_param_guis()

    def add_p_preset(self):
        preset_name, ok = QInputDialog.getText(self, 'New Parameter-Preset',
                                               'Enter a name for a new Parameter-Preset')
        if ok:
            self.mw.pr.p_preset = preset_name
            self.mw.pr.load_default_parameters()
            self.p_preset_cmbx.addItem(preset_name)
            self.p_preset_cmbx.setCurrentText(preset_name)
        else:
            pass

    def redraw_param_widgets(self):
        self.general_layout.removeWidget(self.tab_param_widget)
        self.tab_param_widget.close()
        del self.tab_param_widget
        self.dropgroup_params()
        self.add_param_guis()
        self.update_ppreset_cmbx()

    def update_all_param_guis(self):
        for gui_name in self.param_guis:
            param_gui = self.param_guis[gui_name]
            param_gui.read_param()
            param_gui.set_param()

    def reset_all_parameters(self):
        msgbox = QMessageBox.question(self, 'Reset all Parameters?',
                                      'Do you really want to reset all parameters to their default?',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if msgbox == QMessageBox.Yes:
            self.mw.pr.load_default_parameters()
            self.update_all_param_guis()


class SysInfoMsg(QDialog):
    def __init__(self, main_win):
        super().__init__(main_win)
        layout = QVBoxLayout()
        self.show_widget = QTextEdit()
        self.show_widget.setReadOnly(True)
        layout.addWidget(self.show_widget)

        close_bt = QPushButton('Close')
        close_bt.clicked.connect(self.close)
        layout.addWidget(close_bt)

        # Set geometry to ratio of screen-geometry
        set_ratio_geometry(0.4, self)

        self.setLayout(layout)
        self.show()

    def add_text(self, text):
        self.show_widget.insertPlainText(text)


class QuickGuide(QDialog):
    def __init__(self, main_win):
        super().__init__(main_win)
        layout = QVBoxLayout()

        text = '<b>Quick-Guide</b><br>' \
               '1. Use the Subject-Wizard to add Subjects and the Subject-Dicts<br>' \
               '2. Select the files you want to execute<br>' \
               '3. Select the functions to execute<br>' \
               '4. If you want to show plots, check Show Plots<br>' \
               '5. For Source-Space-Operations, you need to run MRI-Coregistration from the Input-Menu<br>' \
               '6. For Grand-Averages add a group and add the files, to which you want apply the grand-average'

        self.label = QLabel(text)
        layout.addWidget(self.label)

        ok_bt = QPushButton('OK')
        ok_bt.clicked.connect(self.close)
        layout.addWidget(ok_bt)

        self.setLayout(layout)
        self.open()


class RawInfo(QDialog):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.mw = main_win
        self.info_string = None

        set_ratio_geometry(0.6, self)

        self.init_ui()
        self.open()

    def init_ui(self):
        layout = QGridLayout()
        meeg_list = SimpleList(self.mw.pr.all_meeg)
        meeg_list.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        meeg_list.currentChanged.connect(self.meeg_selected)
        layout.addWidget(meeg_list, 0, 0)

        self.info_label = QTextEdit()
        self.info_label.setReadOnly(True)
        self.info_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        layout.addWidget(self.info_label, 0, 1)

        close_bt = QPushButton('Close')
        close_bt.clicked.connect(self.close)
        layout.addWidget(close_bt, 1, 0, 1, 2)

        self.setLayout(layout)

    def meeg_selected(self, meeg_name):
        # Get size in Mebibytes of all files associated to this
        meeg = MEEG(meeg_name, self.mw)
        info = meeg.load_info()
        fp = meeg.file_parameters
        meeg.get_existing_paths()
        other_infos = dict()

        sizes = list()
        for path_type in meeg.existing_paths:
            for path in meeg.existing_paths[path_type]:
                file_name = Path(path).name
                if file_name in fp and 'SIZE' in fp[file_name]:
                    sizes.append(fp[file_name]['SIZE'])
        other_infos['no_files'] = len(sizes)

        sizes_sum = sum(sizes)
        if sizes_sum / 1024 < 1000:
            other_infos['size'] = f'{int(sizes_sum / 1024)}'
            size_unit = 'KB'
        else:
            other_infos['size'] = f'{int(sizes_sum / 1024 ** 2)}'
            size_unit = 'MB'

        ch_type_counter = Counter([mne.io.pick.channel_type(info, idx) for idx in range(len(info['chs']))])
        other_infos['ch_types'] = ', '.join([f'{key}: {value}' for key, value in ch_type_counter.items()])

        key_list = [('no_files', 'Size of all associated files'),
                    ('size', 'Size of all associated files', size_unit),
                    ('proj_name', 'Project-Name'),
                    ('experimenter', 'Experimenter'),
                    ('line_freq', 'Powerline-Frequency', 'Hz'),
                    ('sfreq', 'Samplerate', 'Hz'),
                    ('highpass', 'Highpass', 'Hz'),
                    ('lowpass', 'Lowpass', 'Hz'),
                    ('nchan', 'Number of channels'),
                    ('ch_types', 'Channel-Types'),
                    ('subject_info', 'Subject-Info'),
                    ('device_info', 'Device-Info'),
                    ('helium_info', 'Helium-Info')]

        self.info_string = f'<h1>{meeg_name}</h1>'

        for key_tuple in key_list:
            key = key_tuple[0]
            if key in info:
                value = info[key]
            elif key in other_infos:
                value = other_infos[key]
            else:
                value = None

            if len(key_tuple) == 2:
                self.info_string += f'<b>{key_tuple[1]}:</b> {value}<br>'
            else:
                self.info_string += f'<b>{key_tuple[1]}:</b> {value} <i>{key_tuple[2]}</i><br>'

        self.info_label.setHtml(self.info_string)
