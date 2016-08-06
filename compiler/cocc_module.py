#coding=gbk

"""
����ģ��
"""

import os
import cocc_common
import cocc_token
import cocc_type
import cocc_stmt
import cocc_expr

_INC_DEC_OP_METHOD_NAME_SET = set(["inc", "dec"])
_UNARY_NUM_OP_METHOD_NAME_SET = set(["inv", "neg", "pos"])
_UNARY_OP_METHOD_NAME_SET = _INC_DEC_OP_METHOD_NAME_SET | _UNARY_NUM_OP_METHOD_NAME_SET
_BINOCULAR_NUM_OP_METHOD_NAME_SET = set(["add", "sub", "mul", "div", "mod", "and", "or", "xor", "shl", "shr"])
_BINOCULAR_NUM_REVERSE_OP_METHOD_NAME_SET = set(["r" + _name for _name in _BINOCULAR_NUM_OP_METHOD_NAME_SET])
_BINOCULAR_NUM_INPLACE_OP_METHOD_NAME_SET = set(["i" + _name for _name in _BINOCULAR_NUM_OP_METHOD_NAME_SET])
_BINOCULAR_CMP_OP_METHOD_NAME_SET = set(["eq", "cmp"])
_BINOCULAR_OP_METHOD_NAME_SET = (set(["item_get"]) | _BINOCULAR_NUM_OP_METHOD_NAME_SET | _BINOCULAR_NUM_REVERSE_OP_METHOD_NAME_SET |
                                 _BINOCULAR_NUM_INPLACE_OP_METHOD_NAME_SET | _BINOCULAR_CMP_OP_METHOD_NAME_SET)
_ITEM_INC_DEC_OP_METHOD_NAME_SET = set(["item_inc", "item_dec"])
_ITEM_ASSIGN_OP_METHOD_NAME_SET = set(["item_set"]) | set(["item_" + _name for _name in _BINOCULAR_NUM_INPLACE_OP_METHOD_NAME_SET])
_OP_METHOD_NAME_SET = (_UNARY_OP_METHOD_NAME_SET | _BINOCULAR_OP_METHOD_NAME_SET | _ITEM_INC_DEC_OP_METHOD_NAME_SET |
                       _ITEM_ASSIGN_OP_METHOD_NAME_SET)

builtins_module = None
module_map = cocc_common.OrderedDict()

def _parse_decr_set(token_list):
    decr_set = set()
    while True:
        t = token_list.peek()
        for decr in "public", "protected", "private", "native", "final", "abstract":
            if t.is_reserved(decr):
                if decr in decr_set:
                    t.syntax_err("�ظ�������'%s'" % decr)
                decr_set.add(decr)
                if len(decr_set & set(["public", "protected", "private"])) > 1:
                    t.syntax_err("ͬʱ���ڶ��Ȩ������")
                token_list.pop()
                break
        else:
            return decr_set

def _parse_arg_map(token_list, dep_module_set):
    arg_map = cocc_common.OrderedDict()
    if token_list.peek().is_sym(")"):
        return arg_map
    while True:
        if token_list.peek().is_reserved("ref"):
            token_list.pop()
            is_ref = True
        else:
            is_ref = False
        type = cocc_type.parse_type(token_list, dep_module_set, is_ref = is_ref)
        if type.name == "void":
            type.token.syntax_err("�������Ͳ���Ϊvoid")
        t, name = token_list.pop_name()
        if name in arg_map:
            t.syntax_err("�������ض���")
        if name in dep_module_set:
            t.syntax_err("�������͵���ģ������ͻ")
        arg_map[name] = type
        t = token_list.peek()
        if t.is_sym(","):
            token_list.pop_sym(",")
            continue
        if t.is_sym(")"):
            return arg_map
        t.syntax_err("��Ҫ','��')'")

def _same_arg_map(arg_map_1, arg_map_2):
    if len(arg_map_1) != len(arg_map_2):
        return False
    for i, tp in enumerate(arg_map_1.itervalues()):
        other_tp = arg_map_2.value_at(i)
        if tp != other_tp:
            return False
    return True

def _parse_expr_token_list(token_list):
    expr_token_list = cocc_token.TokenList(token_list.src_file)
    stk = []
    while True:
        t = token_list.pop()
        expr_token_list.append(t)
        if t.is_sym and t.value in (";", ",") and not stk:
            sym = t.value
            return expr_token_list, sym
        if t.is_sym("("):
            stk.append(t)
        if t.is_sym(")"):
            if not stk:
                t.syntax_err("δƥ���')'")
            stk.pop()

def _parse_expr_list_token_list(token_list):
    expr_list_token_list = cocc_token.TokenList(token_list.src_file)
    stk = []
    while True:
        t = token_list.pop()
        expr_list_token_list.append(t)
        if t.is_sym("("):
            stk.append(t)
        if t.is_sym(")"):
            if not stk:
                return expr_list_token_list
            stk.pop()

def _parse_block_token_list(token_list):
    block_token_list = cocc_token.TokenList(token_list.src_file)
    stk = []
    while True:
        t = token_list.pop()
        block_token_list.append(t)
        if t.is_sym("{"):
            stk.append(t)
        if t.is_sym("}"):
            if not stk:
                return block_token_list
            stk.pop()

def _get_access_ctrl(decr_set):
    access_ctrl_decr_set = decr_set & set(["public", "protected", "private"])
    assert len(access_ctrl_decr_set) <= 1
    return "private" if len(access_ctrl_decr_set) == 0 else iter(access_ctrl_decr_set).next()

class _Method:
    def __init__(self, name, cls, decr_set, type, arg_map, block_token_list, super_construct_expr_list_token_list = None):
        self.name = name
        self.cls = cls
        self.decr_set = decr_set
        self.access_ctrl = _get_access_ctrl(decr_set)
        self.type = type
        self.arg_map = arg_map
        self.block_token_list = block_token_list
        self.super_construct_expr_list_token_list = super_construct_expr_list_token_list

    def check_type(self):
        self.type.check(self.cls.module, self.cls)
        for tp in self.arg_map.itervalues():
            tp.check(self.cls.module, self.cls)

    def _check_op_method(self):
        if not self.name.startswith("__op_"):
            return
        op = self.name[5 :]

        assert op in _OP_METHOD_NAME_SET

        #��鷵������
        if op == "eq" and self.type != cocc_type.BOOL_TYPE:
            self.type.token.syntax_err("%s�����ķ������ͱ�����bool" % self.name)
        if op == "cmp" and self.type != cocc_type.INT_TYPE:
            self.type.token.syntax_err("%s�����ķ������ͱ�����int" % self.name)
        if op.startswith("item_") and op != "item_get" and self.type != cocc_type.VOID_TYPE:
            self.type.token.syntax_err("%s�����ķ������ͱ�����void" % self.name)
        if (op in ("inc", "dec", "imod", "ixor", "iand", "imul", "isub", "iadd", "ior", "idiv", "ishl", "ishr") and
            self.type.get_cls() is not self.cls):
            self.type.token.syntax_err("%s�����ķ������ͱ����ǵ�ǰ��" % self.name)

        #����������
        if op in _UNARY_OP_METHOD_NAME_SET and len(self.arg_map) != 0:
            self.type.token.syntax_err("%s������������ֻ����0" % self.name)
        if op in _BINOCULAR_OP_METHOD_NAME_SET and len(self.arg_map) != 1:
            self.type.token.syntax_err("%s������������ֻ����1" % self.name)
        if op in _ITEM_INC_DEC_OP_METHOD_NAME_SET and len(self.arg_map) != 1:
            self.type.token.syntax_err("%s������������ֻ����1" % self.name)
        if op in _ITEM_ASSIGN_OP_METHOD_NAME_SET and len(self.arg_map) != 2:
            self.type.token.syntax_err("%s������������ֻ����2" % self.name)

    def compile(self):
        self._check_op_method()

        if self.super_construct_expr_list_token_list is None:
            self.super_construct_expr_list, self.super_construct_method = None, None
        else:
            self.super_construct_expr_list, self.super_construct_method = cocc_expr.parse_super_construct_expr_list(self)
            self.super_construct_expr_list_token_list.pop_sym(")")
            assert not self.super_construct_expr_list_token_list
        del self.super_construct_expr_list_token_list

        if self.block_token_list is None:
            self.stmt_list = None
        else:
            self.stmt_list = cocc_stmt.parse_stmt_list(self.block_token_list, self.cls.module, self.cls, (self.arg_map.copy(),), 0, self.type)
            self.block_token_list.pop_sym("}")
            assert not self.block_token_list
            self.stmt_list.analyze_non_raw_var((), self.super_construct_method, self.super_construct_expr_list)
        del self.block_token_list

    def to_gcls_inst_method(self, gcls_inst):
        method = _Method(self.name, gcls_inst, self.decr_set, self.type.to_gcls_inst_type(gcls_inst.gtp_map), self.arg_map.copy(), None)
        for name, tp in method.arg_map.iteritems():
            method.arg_map[name] = tp.to_gcls_inst_type(gcls_inst.gtp_map)
        method.stmt_list = None
        del method.block_token_list
        return method

class _Attr:
    def __init__(self, name, cls, decr_set, type):
        self.name = name
        self.cls = cls
        self.decr_set = decr_set
        self.access_ctrl = _get_access_ctrl(decr_set)
        self.type = type

    def check_type(self):
        self.type.check(self.cls.module, self.cls)

    def to_gcls_inst_attr(self, gcls_inst):
        return _Attr(self.name, gcls_inst, self.decr_set, self.type.to_gcls_inst_type(gcls_inst.gtp_map))

class _Class:
    def __init__(self, module, decr_set, name, base_cls_type, gtp_name_list):
        if gtp_name_list:
            assert "native" in decr_set
        self.module = module
        self.decr_set = decr_set
        self.name = name
        self.base_cls_type = base_cls_type
        self.gtp_name_list = gtp_name_list
        self.construct_method = []
        self.destruct_method = None
        self.attr_map = cocc_common.OrderedDict()
        self.method_map = cocc_common.OrderedDict()

    def parse(self, token_list):
        while True:
            t = token_list.peek()
            if t.is_sym("}"):
                break

            #��������
            decr_set = _parse_decr_set(token_list)
            if "native" in decr_set:
                t.syntax_err("�����Ի򷽷����岻��ʹ��native����")

            t = token_list.peek()
            if t.is_sym("~"):
                #��������
                token_list.pop_sym("~")
                if self.destruct_method is not None:
                    t.syntax_err("���������ظ�����")
                if decr_set:
                    t.syntax_err("����������������")
                if "native" in self.decr_set:
                    t.syntax_err("native�಻��Ҫ������������")
                t, name = token_list.pop_name()
                if name != self.name:
                    t.syntax_err("��Ҫ'%s'" % self.name)
                token_list.pop_sym("(")
                self._parse_method(decr_set, None, name, token_list)
                continue
            if t.is_name and t.value == self.name:
                t, name = token_list.pop_name()
                if token_list.peek().is_sym("("):
                    #���췽��
                    if set(["final", "abstract"]) & decr_set:
                        t.syntax_err("���췽��������final��abstract����")
                    token_list.pop_sym("(")
                    self._parse_method(decr_set, cocc_type.VOID_TYPE, name, token_list)
                    continue
                token_list.revert()

            if "abstract" in decr_set:
                if "final" in decr_set:
                    t.syntax_err("final��abstract����ͬʱ����")
                if "final" in self.decr_set:
                    t.syntax_err("final��ķ�����������Ϊabstract")

            #�������Ի򷽷�
            type = cocc_type.parse_type(token_list, self.module.dep_module_set)
            t, name = token_list.pop_name()
            if name == self.name:
                t.syntax_err("���Ի򷽷���������ͬ��")
            self._check_redefine(t, name, token_list.peek().is_sym("("))
            sym_t, sym = token_list.pop_sym()
            if sym == "(":
                #����
                if name.startswith("__op_"):
                    if "final" not in self.decr_set:
                        t.syntax_err("��ֹ�ڷ�final����ʵ�������")
                    if name[5 :] not in _OP_METHOD_NAME_SET:
                        t.syntax_err("�Ƿ��������������'%s'" % name)
                self._parse_method(decr_set, type, name, token_list)
                continue
            if sym in (";", ","):
                #����
                if type.name == "void":
                    t.syntax_err("�������Ͳ���Ϊvoid")
                while True:
                    if name.startswith("__"):
                        t.syntax_err("���Բ�����˫�»��߿�ͷ")
                    if set(["final", "abstract"]) & decr_set:
                        t.syntax_err("���Բ�����final��abstract����")
                    self.attr_map[name] = _Attr(name, self, decr_set, type)
                    if sym == ";":
                        break
                    #�����Զ���
                    assert sym == ","
                    t, name = token_list.pop_name()
                    self._check_redefine(t, name)
                    sym_t, sym = token_list.pop_sym()
                    if sym not in (";", ","):
                        t.syntax_err()
                continue
            t.syntax_err()

    def _parse_method(self, decr_set, type, name, token_list):
        start_token = token_list.peek()
        arg_map = _parse_arg_map(token_list, self.module.dep_module_set)
        token_list.pop_sym(")")
        if "native" in self.decr_set or "abstract" in decr_set:
            if name == self.name and type is cocc_type.VOID_TYPE:
                super_construct_expr_list_token_list = None
            token_list.pop_sym(";")
            block_token_list = None
        else:
            if name == self.name and type is cocc_type.VOID_TYPE:
                #���췽������Ϊ������ǿ��Ҫ��ָ�����๹�췽��
                if self.base_cls_type is None:
                    super_construct_expr_list_token_list = None
                else:
                    token_list.pop_sym(":")
                    t = token_list.pop()
                    if not t.is_reserved("super"):
                        t.syntax_err("��Ҫ��ʽsuper(...)ָ�����๹�췽��")
                    token_list.pop_sym("(")
                    super_construct_expr_list_token_list = _parse_expr_list_token_list(token_list)
            token_list.pop_sym("{")
            block_token_list = _parse_block_token_list(token_list)
        if name == self.name:
            if type is cocc_type.VOID_TYPE:
                #���췽��
                self.construct_method.append(_Method(name, self, decr_set, cocc_type.VOID_TYPE, arg_map, block_token_list,
                                                     super_construct_expr_list_token_list))
            else:
                #��������
                assert type is None
                assert self.destruct_method is None
                assert not decr_set
                if len(arg_map) > 0:
                    start_token.syntax_err("�������������в���")
                self.destruct_method = _Method(name, self, decr_set, cocc_type.VOID_TYPE, arg_map, block_token_list)
        else:
            if name not in self.method_map:
                self.method_map[name] = []
            self.method_map[name].append(_Method(name, self, decr_set, type, arg_map, block_token_list))

    def _check_redefine(self, t, name, is_method = False):
        check_list = (self.attr_map, self.module.dep_module_set)
        if not is_method:
            check_list += (self.method_map,)
        for i in check_list:
            if name in i:
                t.syntax_err("�����ض���")

    def check_type(self):
        if self.base_cls_type is not None:
            self.base_cls_type.check(self.module, self)
        for method in self.construct_method:
            method.check_type()
        #������������Ҫcheck_type
        for attr in self.attr_map.itervalues():
            attr.check_type()
        for method_list in self.method_map.itervalues():
            for method in method_list:
                method.check_type()

    def check_overload(self):
        for i, method in enumerate(self.construct_method):
            for other_method in self.construct_method[i + 1 :]:
                assert self.name == method.name == other_method.name
                if _same_arg_map(method.arg_map, other_method.arg_map):
                    cocc_common.exit("��'%s.%s'�Ĺ��췽������������ͬǩ��������" % (self.module.name, cls.name))
                    
        for name, method_list in self.method_map.iteritems():
            for i, method in enumerate(method_list):
                for other_method in method_list[i + 1 :]:
                    assert name == method.name == other_method.name
                    if _same_arg_map(method.arg_map, other_method.arg_map):
                        cocc_common.exit("��'%s.%s'�ķ���'%s'����������ͬǩ��������" % (self.module.name, cls.name, name))

    def sub_class_check(self):
        if self.base_cls_type is None:
            return

        #����̳�����ͬʱ���ѭ���̳С����췽�����Ƿ�������ִ�е�
        inherit_list = [self]
        while True:
            new_base_cls_type = inherit_list[-1].base_cls_type
            if new_base_cls_type is None:
                break
            new_base_cls = new_base_cls_type.get_cls()
            if "final" in new_base_cls.decr_set:
                cocc_common.exit("��'%s.%s'�̳���һ��final��" % (self.module.name, cls.name))
            for cls in inherit_list:
                if cls is new_base_cls:
                    cocc_common.exit("��'%s.%s'ѭ���̳�" % (cls.module.name, cls.name))
            inherit_list.append(new_base_cls)
        del inherit_list[0]

        for attr in self.attr_map.itervalues():
            for base_cls in inherit_list:
                if attr.name in base_cls.method_map:
                    cocc_common.exit("��'%s.%s'������'%s'�ڻ���'%s.%s'ʵ��Ϊ����" %
                                     (self.module.name, self.name, attr.name, base_cls.module.name, base_cls.name))

        for name, method_list in self.method_map.iteritems():
            for base_cls in inherit_list:
                if name in base_cls.attr_map:
                    cocc_common.exit("��'%s.%s'�ķ���'%s'�ڻ���'%s.%s'ʵ��Ϊ����" %
                                     (self.module.name, self.name, name, base_cls.module.name, base_cls.name))
                if name in base_cls.method_map:
                    base_method_list = base_cls.method_map[name]
                    #�Ի����ÿ��������������������е�ʵ�����
                    for base_method in base_method_list:
                        match_count = 0
                        for method in method_list:
                            if _same_arg_map(base_method.arg_map, method.arg_map):
                                match_count += 1
                                if "final" in base_method.decr_set:
                                    cocc_common.exit("��'%s.%s'�ķ���'%s'�ڻ���'%s.%s'�д�final���ԣ����ɸ���" %
                                                     (self.module.name, self.name, method.name, base_cls.module.name, base_cls.name))
                                if method.access_ctrl != base_method.access_ctrl:
                                    cocc_common.exit("��'%s.%s'�ķ���'%s'�����޸����ڻ���'%s.%s'�ж���Ĵ�ȡ���Ʒ�ʽ����'%s'�޸�Ϊ'%s'" %
                                                     (self.module.name, self.name, method.name, base_cls.module.name, base_cls.name,
                                                      base_method.access_ctrl, method.access_ctrl))
                                if method.type != base_method.type:
                                    cocc_common.exit("��'%s.%s'�ķ���'%s'��������'%s'�����ڻ���'%s.%s'�ж����'%s'��ͬ" %
                                                     (self.module.name, self.name, method.name, method.type, base_cls.module.name,
                                                      base_cls.name, base_method.type))
                        if match_count == 0:
                            cocc_common.warning("��'%s.%s'�ķ���'%s'�������ڻ���'%s.%s'�е���������" %
                                                (self.module.name, self.name, method.name, base_cls.module.name, base_cls.name))
                        else:
                            assert match_count == 1, "match_count == %d" % match_count

    def is_sub_cls_of(self, base_cls):
        cls = self
        while cls.base_cls_type is not None:
            cls = cls.base_cls_type.get_cls()
            if cls is base_cls:
                return True
        return False

    def compile(self):
        for method in self.construct_method:
            method.compile()
        if self.destruct_method is not None:
            self.destruct_method.compile()
        for method_list in self.method_map.itervalues():
            for method in method_list:
                method.compile()

    def _get_method_or_attr(self, name):
        if name in self.method_map:
            return self.method_map[name], None
        if name in self.attr_map:
            return None, self.attr_map[name]
        if self.base_cls_type is None:
            return None, None
        else:
            return self.base_cls_type.get_cls()._get_method_or_attr(name)

    def has_method_or_attr(self, name):
        method, attr = self._get_method_or_attr(name)
        return method is not None or attr is not None

    def get_method_or_attr(self, name, token):
        method, attr = self._get_method_or_attr(name)
        if method is None and attr is None:
            token.syntax_err("��'%s.%s'û�з���������'%s'" % (self.module.name, self.name, name))
        return method, attr

    def is_abstract(self):
        inherit_list = [self]
        while True:
            new_base_cls_type = inherit_list[-1].base_cls_type
            if new_base_cls_type is None:
                break
            new_base_cls = new_base_cls_type.get_cls()
            inherit_list.append(new_base_cls)
        inherit_list.reverse()

        for i, base_cls in enumerate(inherit_list):
            for method_list in base_cls.method_map.itervalues():
                for method in method_list:
                    if "abstract" in method.decr_set:
                        #�����Ƿ���д��
                        overrided = False
                        for cls in inherit_list[i + 1 :]:
                            if method.name in cls.method_map:
                                for m in cls.method_map[method.name]:
                                    assert m.name == method.name
                                    if _same_arg_map(m.arg_map, method.arg_map):
                                        overrided = True
                                        break
                                if overrided:
                                    break
                        if not overrided:
                            return method

class _GenericClassInstance(_Class):
    def __init__(self, gcls, gtp_list):
        assert "native" in gcls.decr_set
        assert gtp_list and len(gcls.gtp_name_list) == len(gtp_list)
        self.gtp_map = dict(zip(gcls.gtp_name_list, gtp_list))
        self.module = gcls.module
        self.decr_set = gcls.decr_set
        self.gcls = gcls
        self.name = gcls.name + "<%s>" % ", ".join([str(gtp) for gtp in gtp_list])
        self.base_cls_type = None if gcls.base_cls_type is None else gcls.base_cls_type.to_gcls_inst_type(self.gtp_map)
        self.construct_method = [method.to_gcls_inst_method(self) for method in gcls.construct_method]
        self.destruct_method = None if gcls.destruct_method is None else gcls.destruct_method.to_gcls_inst_method(self)
        self.attr_map = cocc_common.OrderedDict()
        for name, attr in gcls.attr_map.iteritems():
            assert name == attr.name
            self.attr_map[name] = attr.to_gcls_inst_attr(self)
        self.method_map = cocc_common.OrderedDict()
        for name, method_list in gcls.method_map.iteritems():
            self.method_map[name] = ml = []
            for method in method_list:
                assert name == method.name
                ml.append(method.to_gcls_inst_method(self))

class _Typedef:
    STAT_TO_EXPAND = object()
    STAT_EXPANDING = object()
    STAT_EXPANDED = object()

    def __init__(self, name, module, decr_set, type):
        self.name = name
        self.module = module
        self.decr_set = decr_set
        self.type = type
        self.stat = self.STAT_TO_EXPAND

    def expand(self):
        if self.stat == self.STAT_EXPANDING:
            cocc_common.exit("'%s.%s'����ѭ��typedef" % (self.module.name, self.name))
        if self.stat == self.STAT_EXPANDED:
            return
        assert self.stat == self.STAT_TO_EXPAND
        self.stat = self.STAT_EXPANDING
        self.type = self._expand(self.type)
        self.stat = self.STAT_EXPANDED

    def _expand(self, type):
        if type.token.is_reserved:
            #�ڽ�����
            return type
        type_module_name = type.module_name
        if type_module_name is None:
            type_module = self.module
        else:
            type_module = module_map[type_module_name]
        if type.name in type_module.typedef_map:
            #ֱ��Ƕ��typedef
            if type.gtp_list:
                type.token.syntax_err("'%s.%s'����һ��typedef���ͣ����Ƿ�����" % (type_module.name, type.name))
            tpdef = type_module.typedef_map[type.name]
            tpdef.expand()
            return tpdef.type
        #���ڽ�����typedef��ֻ����gtp_list��Ƕ��
        for i, gtp in enumerate(type.gtp_list):
            type.gtp_list[i] = self._expand(gtp)
        return type

    def check_type(self):
        assert self.stat == self.STAT_EXPANDED
        self.type.check(self.module)

class _Func:
    def __init__(self, name, module, decr_set, type, arg_map, block_token_list):
        self.name = name
        self.module = module
        self.decr_set = decr_set
        self.type = type
        self.arg_map = arg_map
        self.block_token_list = block_token_list

    def check_type(self):
        self.type.check(self.module)
        for tp in self.arg_map.itervalues():
            tp.check(self.module)

    def compile(self):
        if self.block_token_list is None:
            self.stmt_list = None
        else:
            self.stmt_list = cocc_stmt.parse_stmt_list(self.block_token_list, self.module, None, (self.arg_map.copy(),), 0, self.type)
            self.block_token_list.pop_sym("}")
            assert not self.block_token_list
            self.stmt_list.analyze_non_raw_var(())
        del self.block_token_list

class _GlobalVar:
    def __init__(self, name, module, decr_set, type, expr_token_list):
        self.name = name
        self.module = module
        self.decr_set = decr_set
        self.type = type
        self.expr_token_list = expr_token_list

    def check_type(self):
        self.type.check(self.module)

    def compile(self):
        if self.expr_token_list is None:
            self.expr = None
        else:
            self.expr = cocc_expr.parse_expr(self.expr_token_list, (), None, self.module, self.type)
            t, sym = self.expr_token_list.pop_sym()
            assert not self.expr_token_list and sym in (";", ",")
        del self.expr_token_list

class Module:
    def __init__(self, file_path_name):
        self.dir, file_name = os.path.split(file_path_name)
        assert file_name.endswith(".coc")
        self.name = file_name[: -4]
        self._precompile(file_path_name)
        if self.name == "__builtins":
            #�ڽ�ģ����Ҫ��һЩ��Ҫ�ļ��
            if "String" not in self.class_map: #������String��
                cocc_common.exit("�ڽ�ģ��ȱ��String��")
            str_cls = self.class_map["String"]
            if "format" in str_cls.attr_map or "format" in str_cls.method_map:
                cocc_common.exit("String���format���������ڽ�������������ֹ��ʽ����")

    def _precompile(self, file_path_name):
        #����token�б���������
        token_list = cocc_token.parse_token_list(file_path_name)
        self._parse_text(token_list)

    def _parse_text(self, token_list):
        self.dep_module_set = set()
        import_end = False
        self.class_map = cocc_common.OrderedDict()
        self.gcls_inst_map = cocc_common.OrderedDict()
        self.typedef_map = cocc_common.OrderedDict()
        self.func_map = cocc_common.OrderedDict()
        self.global_var_map = cocc_common.OrderedDict()
        while token_list:
            #����import
            t = token_list.peek()
            if t.is_reserved("import"):
                #import
                if import_end:
                    t.syntax_err("import������ģ�������ǰ��")
                self._parse_import(token_list)
                continue
            import_end = True

            #��������
            decr_set = _parse_decr_set(token_list)

            #�������ֶ���
            t = token_list.peek()
            if t.is_reserved("class"):
                #������
                if decr_set - set(["public", "native", "final"]):
                    t.syntax_err("��ֻ����public��native��final����")
                self._parse_class(decr_set, token_list)
                continue

            if t.is_reserved("typedef"):
                #����typedef
                if decr_set - set(["public"]):
                    t.syntax_err("typedefֻ����public����")
                self._parse_typedef(decr_set, token_list)
                continue

            #�����Ǻ�����ȫ�ֱ���
            type = cocc_type.parse_type(token_list, self.dep_module_set)
            t, name = token_list.pop_name()
            self._check_redefine(t, name, token_list.peek().is_sym("("))
            t, sym = token_list.pop_sym()
            if sym == "(":
                #����
                if decr_set - set(["public", "native"]):
                    t.syntax_err("����ֻ����public��native����")
                self._parse_func(decr_set, type, name, token_list)
                continue
            if sym in (";", "=", ","):
                #ȫ�ֱ���
                if decr_set - set(["public", "native", "final"]):
                    t.syntax_err("ȫ�ֱ���ֻ����public��native��final����")
                if type.name == "void":
                    t.syntax_err("�������Ͳ���Ϊvoid")
                while True:
                    if sym == "=":
                        if "native" in decr_set:
                            t.syntax_err("���ܳ�ʼ��nativeȫ�ֱ���")
                        expr_token_list, sym = _parse_expr_token_list(token_list)
                    else:
                        if "native" not in decr_set:
                            t.syntax_err("��nativeȫ�ֱ���������ʽ��ʼ��")
                        expr_token_list = None
                    self.global_var_map[name] = _GlobalVar(name, self, decr_set, type, expr_token_list)
                    if sym == ";":
                        break
                    #�����˶����������������
                    assert sym == ","
                    t, name = token_list.pop_name()
                    self._check_redefine(t, name)
                    t, sym = token_list.pop_sym()
                    if sym not in (";", "=", ","):
                        t.syntax_err()
                continue
            t.syntax_err()

    def _parse_func(self, decr_set, type, name, token_list):
        arg_map = _parse_arg_map(token_list, self.dep_module_set)
        token_list.pop_sym(")")
        if "native" in decr_set:
            token_list.pop_sym(";")
            block_token_list = None
        else:
            token_list.pop_sym("{")
            block_token_list = _parse_block_token_list(token_list)
        if name not in self.func_map:
            self.func_map[name] = []
        self.func_map[name].append(_Func(name, self, decr_set, type, arg_map, block_token_list))

    def _parse_typedef(self, decr_set, token_list):
        t = token_list.pop()
        assert t.is_reserved("typedef")
        t = token_list.peek()
        tp = cocc_type.parse_type(token_list, self.dep_module_set)
        if tp.is_array:
            t.syntax_err("���ܶ�������typedef")
        t, name = token_list.pop_name()
        self._check_redefine(t, name)
        self.typedef_map[name] = _Typedef(name, self, decr_set, tp)
        token_list.pop_sym(";")

    def _parse_class(self, cls_decr_set, token_list):
        t = token_list.pop()
        assert t.is_reserved("class")
        t, cls_name = token_list.pop_name()
        self._check_redefine(t, cls_name)
        gtp_name_list = []
        t, sym = token_list.pop_sym()
        if sym == "<":
            if "native" not in cls_decr_set:
                t.syntax_err("�����������nativeʵ��")
            while True:
                t, name = token_list.pop_name()
                if name in self.dep_module_set:
                    t.syntax_err("�������뵼��ģ������")
                gtp_name_list.append(name)
                t, sym = token_list.pop_sym()
                if sym == ",":
                    continue
                if sym == ">":
                    break
                t.syntax_err("��Ҫ'>'��','")
            t, sym = token_list.pop_sym()
        base_cls_type = None
        if sym == ":":
            #���ڼ̳й�ϵ
            t = token_list.peek()
            base_cls_type = cocc_type.parse_type(token_list, self.dep_module_set)
            if base_cls_type.is_array:
                t.syntax_err("�޷��̳�����")
            if base_cls_type.token.is_reserved:
                t.syntax_err("�޷��̳�����'%s'" % base_cls_type.name)
            t, sym = token_list.pop_sym()
        if sym != "{":
            t.syntax_err("��Ҫ'{'")
        cls = _Class(self, cls_decr_set, cls_name, base_cls_type, gtp_name_list)
        cls.parse(token_list)
        token_list.pop_sym("}")
        self.class_map[cls_name] = cls

    def _check_redefine(self, t, name, is_func = False):
        check_list = self.dep_module_set, self.class_map, self.typedef_map, self.global_var_map
        if not is_func:
            check_list += (self.func_map,)
        for i in check_list:
            if name in i:
                t.syntax_err("�����ض���")

    def _parse_import(self, token_list):
        t = token_list.pop()
        assert t.is_reserved("import")
        while True:
            t, name = token_list.pop_name()
            if name in self.dep_module_set:
                t.syntax_err("ģ���ظ�import")
            self.dep_module_set.add(name)
            t, sym = token_list.pop_sym()
            if sym == ";":
                return
            if sym != ",":
                t.syntax_err("��Ҫ';'��','")

    def _items(self):
        for map in self.class_map, self.func_map, self.global_var_map:
            for item in map.itervalues():
                if map is self.func_map:
                    for func in item:
                        yield func
                else:
                    yield item

    def expand_typedef(self):
        for tpdef in self.typedef_map.itervalues():
            tpdef.expand()

    def check_type_for_typedef(self):
        for tpdef in self.typedef_map.itervalues():
            tpdef.check_type()

    def check_type(self):
        for item in self._items():
            item.check_type()

    def check_overload(self):
        for cls in self.class_map.itervalues():
            cls.check_overload()
        for name, func_list in self.func_map.iteritems():
            for i, func in enumerate(func_list):
                for other_func in func_list[i + 1 :]:
                    assert name == func.name == other_func.name
                    if _same_arg_map(func.arg_map, other_func.arg_map):
                        cocc_common.exit("ģ��'%s'�ķ���'%s'����������ͬǩ��������" % (self.name, name))

    def check_sub_class(self):
        for cls in self.class_map.itervalues():
            cls.sub_class_check()

    def compile(self):
        self.literal_str_list = []
        for item in self._items():
            item.compile()

    def has_type_or_typedef(self, name):
        return name in self.class_map or name in self.typedef_map

    def get_typedef(self, type):
        if type.name not in self.typedef_map:
            return None
        return self.typedef_map[type.name]

    def get_type(self, type):
        if type.name not in self.class_map:
            return None
        cls = self.class_map[type.name]

        if cls.gtp_name_list:
            if type.gtp_list:
                if len(cls.gtp_name_list) != len(type.gtp_list):
                    type.token.syntax_err("���Ͳ�������������Ҫ%d����������%d��" % (len(cls.gtp_name_list), len(type.gtp_list)))
            else:
                type.token.syntax_err("������'%s.%s'�޷�����ʹ��" % (self.name, cls.name))
        else:
            if type.gtp_list:
                type.token.syntax_err("'%s.%s'���Ƿ�����" % (self.name, cls.name))

        assert len(cls.gtp_name_list) == len(type.gtp_list)
        if not cls.gtp_name_list:
            return cls

        gcls_key = id(cls),
        for tp in type.gtp_list:
            array_dim_count = tp.array_dim_count
            while tp.is_array:
                tp = tp.to_elem_type()
            if tp.token.is_reserved:
                gcls_key += tp.name, array_dim_count
            else:
                gcls_key += id(tp.get_cls()), array_dim_count
        if gcls_key in self.gcls_inst_map:
            return self.gcls_inst_map[gcls_key]
        gcls_inst = _GenericClassInstance(cls, type.gtp_list)
        gcls_inst.check_overload()
        gcls_inst.sub_class_check()
        self.gcls_inst_map[gcls_key] = gcls_inst
        return gcls_inst

    def get_func_or_global_var(self, name, token):
        if name in self.func_map:
            return self.func_map[name], None
        if name in self.global_var_map:
            return None, self.global_var_map[name]
        token.syntax_err("��Ҫ������ȫ�ֱ���")

    def has_func_or_global_var(self, name):
        return name in self.func_map or name in self.global_var_map

    def has_native_item(self):
        for item in self._items():
            if "native" in item.decr_set:
                return True
        return False
