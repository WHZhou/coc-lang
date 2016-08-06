#coding=gbk

"""
��������ģ��
"""

import sys
import getopt
import os
import cocc_common
import cocc_module
import cocc_type
import cocc_output

def _show_usage_and_exit():
    cocc_common.exit("ʹ�÷�����%s ��ģ��.coc" % sys.argv[0])

def _find_module_file(module_dir_list, module_name):
    #��Ŀ¼����
    for module_dir in module_dir_list:
        module_file_path_name = os.path.join(module_dir, module_name) + ".coc"
        if os.path.exists(module_file_path_name):
            return module_file_path_name
    cocc_common.exit("�Ҳ���ģ�飺%s" % module_name)

def main():
    #���������в���
    opt_list, args = getopt.getopt(sys.argv[1 :], "", [])

    if len(args) != 1:
        _show_usage_and_exit()

    #ͨ��Ŀ¼
    compiler_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    lib_dir = os.path.join(os.path.dirname(compiler_dir), "lib")

    #Ԥ����builtins��ģ��
    cocc_module.builtins_module = cocc_module.Module(os.path.join(lib_dir, "__builtins.coc"))
    cocc_module.module_map[cocc_module.builtins_module.name] = cocc_module.builtins_module
    cocc_module.module_map["concurrent"] = cocc_module.Module(os.path.join(lib_dir, "concurrent.coc"))

    #�ȴ�����ģ��
    main_file_path_name = os.path.abspath(args[0])
    if not main_file_path_name.endswith(".coc"):
        cocc_common.exit("�Ƿ�����ģ���ļ���[%s]" % main_file_path_name)
    if not os.path.exists(main_file_path_name):
        cocc_common.exit("�Ҳ�����ģ���ļ�[%s]" % main_file_path_name)
    main_module = cocc_module.Module(main_file_path_name)
    cocc_module.module_map[main_module.name] = main_module

    #ģ����ҵ�Ŀ¼�б�
    src_dir = os.path.dirname(main_file_path_name)
    module_dir_list = [src_dir, lib_dir]

    #�ҵ���Ԥ���������漰����ģ��
    compiling_set = main_module.dep_module_set #��ҪԤ�����ģ��������
    while compiling_set:
        new_compiling_set = set()
        for module_name in compiling_set:
            if module_name in cocc_module.module_map:
                #��Ԥ�����
                continue
            module_file_path_name = _find_module_file(module_dir_list, module_name)
            cocc_module.module_map[module_name] = m = cocc_module.Module(module_file_path_name)
            new_compiling_set |= m.dep_module_set
        compiling_set = new_compiling_set

    #����չǶ��typedef��Ȼ�󵥶���typedef��type����check
    cocc_module.builtins_module.expand_typedef()
    for m in cocc_module.module_map.itervalues():
        if m is not cocc_module.builtins_module:
            m.expand_typedef()
    cocc_module.builtins_module.expand_typedef()
    for m in cocc_module.module_map.itervalues():
        if m is not cocc_module.builtins_module:
            m.check_type_for_typedef()

    #ͳһcheck_type
    cocc_module.builtins_module.check_type()
    for m in cocc_module.module_map.itervalues():
        if m is not cocc_module.builtins_module:
            m.check_type()

    #��������Ƿ�������
    cocc_module.builtins_module.check_overload()
    for m in cocc_module.module_map.itervalues():
        if m is not cocc_module.builtins_module:
            m.check_overload()

    #��ģ��main�������
    if "main" not in main_module.func_map:
        cocc_common.exit("��ģ��[%s]û��main����" % main_module.name)
    main_func_list = main_module.func_map["main"]
    assert main_func_list
    if len(main_func_list) != 1:
        cocc_common.exit("��ģ��[%s]��main������ֹ����" % main_module.name)
    main_func = main_func_list[0]
    if main_func.type != cocc_type.INT_TYPE:
        cocc_common.exit("��ģ��[%s]��main�����������ͱ���Ϊint" % main_module.name)
    if len(main_func.arg_map) != 1:
        cocc_common.exit("��ģ��[%s]��main����ֻ����һ������Ϊ'String[]'�Ĳ���" % main_module.name)
    tp = main_func.arg_map.itervalues().next()
    if tp.is_ref or tp.array_dim_count != 1 or tp.to_elem_type() != cocc_type.STR_TYPE:
        cocc_common.exit("��ģ��[%s]��main�����Ĳ������ͱ���Ϊ'String[]'" % main_module.name)
    if "public" not in main_func.decr_set:
        cocc_common.exit("��ģ��[%s]��main����������public��" % main_module.name)

    #�������ļ̳��Ƿ�Ϸ�
    cocc_module.builtins_module.check_sub_class()
    for m in cocc_module.module_map.itervalues():
        if m is not cocc_module.builtins_module:
            m.check_sub_class()

    #todo������һЩģ��Ԫ�صļ��ͽ�һ��Ԥ����

    #��ʽ�����ģ��
    cocc_module.builtins_module.compile()
    for m in cocc_module.module_map.itervalues():
        if m is not cocc_module.builtins_module:
            m.compile()

    cocc_output.out_dir = os.path.join(src_dir, main_module.name)
    cocc_output.runtime_dir = os.path.join(os.path.dirname(lib_dir), "runtime")
    cocc_output.output(main_module.name)

if __name__ == "__main__":
    main()
