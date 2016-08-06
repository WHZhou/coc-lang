#coding=gbk

"""
�������
"""

import cocc_module

_BASE_TYPE_LIST = ("void", "bool", "byte", "ubyte", "char", "short", "ushort", "int", "uint", "long", "ulong", "float", "double", "ldouble")

#�������͵Ŀ�ת����
_BASE_TYPE_CONVERT_TBL = {"byte" : set(["short", "int", "long", "float", "double", "ldouble"]),
                          "ubyte" : set(["short", "ushort", "int", "uint", "long", "ulong", "float", "double", "ldouble"]),
                          "char" : set(["short", "int", "long", "float", "double", "ldouble"]),
                          "short" : set(["int", "long", "float", "double", "ldouble"]),
                          "ushort" : set(["int", "uint", "long", "ulong", "float", "double", "ldouble"]),
                          "int" : set(["long", "float", "double", "ldouble"]),
                          "uint" : set(["long", "ulong", "float", "double", "ldouble"]),
                          "long" : set(["float", "double", "ldouble"]),
                          "ulong" : set(["float", "double", "ldouble"]),
                          "float" : set(["double", "ldouble"]),
                          "double" : set(["ldouble"]),
                          "literal_byte" : set(["byte", "ubyte", "char", "short", "ushort", "int", "uint", "long", "ulong", "float", "double",
                                                "ldouble"]),
                          "literal_ubyte" : set(["ubyte", "short", "ushort", "int", "uint", "long", "ulong", "float", "double", "ldouble"]),
                          "literal_short" : set(["short", "ushort", "int", "uint", "long", "ulong", "float", "double", "ldouble"]),
                          "literal_ushort" : set(["ushort", "int", "uint", "long", "ulong", "float", "double", "ldouble"]),
                          "literal_int" : set(["int", "uint", "long", "ulong", "float", "double", "ldouble"])}

class _GenericInstanceClass:
    def __init__(self, cls, gtp_list):
        self.cls = cls
        self.gtp_list = gtp_list

class _Type:
    def __init__(self, (name_token, name), token_list, dep_module_set, module_name = None, non_array = False, is_ref = False):
        self.token = name_token
        self.name = name
        self.module_name = module_name
        self.array_dim_count = 0
        self.gtp_list = []
        if not self.token.is_reserved and token_list and token_list.peek().is_sym("<"):
            #�������Ͳ���
            token_list.pop_sym("<")
            while True:
                self.gtp_list.append(parse_type(token_list, dep_module_set))
                t = token_list.pop()
                if t.is_sym(","):
                    continue
                if t.is_sym(">"):
                    break
                if t.is_sym(">>"):
                    token_list.split_shr_sym()
                    break
                t.syntax_err("��Ҫ','��'>'")
        if not non_array:
            while token_list and token_list.peek().is_sym("["):
                if self.name == "void":
                    token_list.peek().syntax_err("�޷�����void������")
                if self.name == "null":
                    raise Exception("Bug")
                token_list.pop_sym("[")
                token_list.pop_sym("]")
                self.array_dim_count += 1
        self.is_ref = is_ref
        self.is_gtp_name = False
        self.set_is_XXX()

    def set_is_XXX(self):
        self.is_array = self.array_dim_count > 0
        self.is_null = self.token.is_reserved("null")
        self.is_obj_type = self.is_null or self.is_array or self.token.is_name
        self.is_void = self.token.is_reserved("void")
        self.is_bool_type = self.token.is_reserved("bool") and self.array_dim_count == 0
        self.is_integer_type = (self.token.is_reserved and
                                self.name in ("byte", "ubyte", "char", "short", "ushort", "int", "uint", "long", "ulong", "literal_byte",
                                              "literal_ubyte", "literal_short", "literal_ushort", "literal_int") and
                                self.array_dim_count == 0)
        self.is_float_point_type = self.token.is_reserved and self.name in ("float", "double", "ldouble") and self.array_dim_count == 0
        self.is_number_type = self.is_integer_type or self.is_float_point_type
        self.can_inc_dec = self.is_integer_type

    def _copy_from(self, tp):
        self.token = tp.token
        self.name = tp.name
        self.module_name = tp.module_name
        self.array_dim_count = tp.array_dim_count
        self.gtp_list = tp.gtp_list
        assert not tp.is_ref
        assert not tp.is_gtp_name
        self.set_is_XXX()

    def __repr__(self):
        assert not self.is_gtp_name
        s = self.name
        if self.module_name is not None:
            s = self.module_name + "." + s
        if self.gtp_list:
            s += "<%s>" % ", ".join([str(tp) for tp in self.gtp_list])
        s += "[]" * self.array_dim_count
        return s
    __str__ = __repr__

    def __eq__(self, other):
        assert not self.is_gtp_name
        return (self.name == other.name and self.module_name == other.module_name and self.gtp_list == other.gtp_list and
                self.array_dim_count == other.array_dim_count)

    def __ne__(self, other):
        return not self == other

    def to_array_type(self, array_dim_count):
        assert self.array_dim_count == 0
        tp = _Type((self.token, self.name), None, None, self.module_name)
        tp.gtp_list = self.gtp_list
        tp.array_dim_count = array_dim_count
        tp.set_is_XXX()
        return tp

    def to_elem_type(self):
        assert self.array_dim_count > 0
        tp = _Type((self.token, self.name), None, None, self.module_name)
        tp.gtp_list = self.gtp_list
        tp.array_dim_count = self.array_dim_count - 1
        tp.set_is_XXX()
        return tp

    def to_gcls_inst_type(self, gtp_map):
        if self.name in gtp_map:
            assert self.token.is_name and self.module_name is None and not self.gtp_list
            return gtp_map[self.name]
        if not self.gtp_list:
            return self
        tp = _Type((self.token, self.name), None, None, self.module_name)
        tp.gtp_list = [gtp.to_gcls_inst_type(gtp_map) for gtp in self.gtp_list]
        tp.set_is_XXX()
        return tp

    def get_cls(self):
        assert self.token.is_name and self.module_name is not None and not self.is_array
        m = cocc_module.module_map[self.module_name]
        tp = m.get_type(self)
        assert tp is not None
        return tp

    def check(self, curr_module, cls = None):
        if cls is not None:
            assert cls.module is curr_module
        if self.token.is_reserved:
            return
        assert self.token.is_name
        if self.module_name is None:
            if cls is not None and self.name in cls.gtp_name_list:
                self.is_gtp_name = True
                if self.gtp_list:
                    self.token.syntax_err("�����ββ�����Ϊ������ʹ��")
                return
            find_path = curr_module, cocc_module.builtins_module
        else:
            find_path = cocc_module.module_map[self.module_name],
        for m in find_path:
            tpdef = m.get_typedef(self)
            if tpdef is not None:
                if self.gtp_list:
                    self.token.syntax_err("'%s.%s'���Ƿ�����" % (m.name, tpdef.name))
                if m is not curr_module:
                    #�ǵ�ǰģ�飬���Ȩ��
                    if "public" not in tpdef.decr_set:
                        self.token.syntax_err("�޷�ʹ������'%s'��û��Ȩ��" % self)
                self._copy_from(tpdef.type)
                break
            tp = m.get_type(self)
            if tp is not None:
                self.module_name = m.name #check��ͬʱҲ������ģ������ͱ�׼��
                if m is not curr_module:
                    #�ǵ�ǰģ�飬���Ȩ��
                    if "public" not in tp.decr_set:
                        self.token.syntax_err("�޷�ʹ������'%s'��û��Ȩ��" % self)
                if not self.gtp_list:
                    assert not tp.gtp_name_list
                break
        else:
            self.token.syntax_err("��Ч������'%s'" % self)
        for tp in self.gtp_list:
            tp.check(curr_module, cls)

    def can_force_convert_from(self, type):
        if self.can_convert_from(type):
            return True
        #����ֻ��ⲻ����ʽת������ǿ��ת���Ĳ��ּ���
        if self.is_void:
            #�κ����Ͷ�����תvoid
            return True
        if self.is_number_type and type.is_number_type:
            #��ֵ���Ϳɻ���ǿת
            return True
        if self.is_array or type.is_array:
            #���������Ҳ�����ʽת���򲻿���ǿת��
            return False
        if self.is_obj_type and type.is_obj_type:
            #����������������null type����type����self�����࣬���Ǳ�����bug
            if self.get_cls().is_sub_cls_of(type.get_cls()):
                #���ൽ�����ǿת
                return True
        return False

    def can_convert_from(self, type):
        if self.module_name is None:
            assert self.token.is_reserved
        else:
            assert self.token.is_name
        if self == type:
            #��ȫһ��
            return True
        if self.is_obj_type and type.is_null:
            #����nullֱ�Ӹ�ֵ�����ж���
            return True
        if self.array_dim_count != type.array_dim_count:
            #��ͬά�ȵ�����϶�����ת��
            return False
        if self.array_dim_count > 0:
            #��ͬ���͵�����Ҳ���ܻ���ת
            return False
        if self.module_name is None:
            if type.module_name is not None:
                return False #�������ͺͶ����޷�����ת��
            #�����������ͣ��ж��¼�����
            if type.name not in _BASE_TYPE_CONVERT_TBL:
                return False
            return self.name in _BASE_TYPE_CONVERT_TBL[type.name]
        if type.module_name is None:
            return False #�������ͺͶ����޷�����ת��
        return type.get_cls().is_sub_cls_of(self.get_cls())

    def check_convert_from(self, type, token):
        if not self.can_convert_from(type):
            token.syntax_err("����'%s'�޷���ʽת��Ϊ'%s'" % (type, self))

class _FakeReservedToken:
    def __init__(self, tp):
        self._tp = tp
    def is_reserved(self, tp):
        return self._tp == tp
    is_name = False

class _FakeNonReservedToken:
    def __init__(self, tp):
        self._tp = tp

        class IsReserved:
            def __nonzero__(self):
                return False
            def __call__(self, word):
                return False

        self.is_reserved = IsReserved()

    is_name = True

for _tp in ("null", "void", "bool", "byte", "ubyte", "char", "short", "ushort", "int", "uint", "long", "ulong", "float", "double", "ldouble",
            "literal_byte", "literal_ubyte", "literal_short", "literal_ushort", "literal_int"):
    exec '%s_TYPE = _Type((_FakeReservedToken("%s"), "%s"), None, None)' % (_tp.upper(), _tp, _tp)
del _tp
STR_TYPE = _Type((_FakeNonReservedToken("String"), "String"), None, None, module_name = "__builtins")

def parse_type(token_list, dep_module_set, is_ref = False):
    t = token_list.pop()
    if t.is_reserved and t.value in _BASE_TYPE_LIST:
        return _Type((t, t.value), token_list, dep_module_set, is_ref = is_ref)
    if t.is_name:
        if t.value in dep_module_set:
            token_list.pop_sym(".")
            return _Type(token_list.pop_name(), token_list, dep_module_set, t.value, is_ref = is_ref)
        return _Type((t, t.value), token_list, dep_module_set, is_ref = is_ref)
    t.syntax_err()

def parse_non_array_type(token_list, dep_module_set):
    t = token_list.pop()
    if t.is_reserved and t.value in _BASE_TYPE_LIST:
        return _Type((t, t.value), token_list, dep_module_set, non_array = True)
    if t.is_name:
        if t.value in dep_module_set:
            token_list.pop_sym(".")
            return _Type(token_list.pop_name(), token_list, dep_module_set, t.value, non_array = True)
        return _Type((t, t.value), token_list, dep_module_set, non_array = True)
    t.syntax_err()

def _try_parse_type(token_list, curr_module):
    t = token_list.pop()
    if t.is_reserved and t.value in _BASE_TYPE_LIST:
        return _Type((t, t.value), token_list, curr_module.dep_module_set)
    if t.is_name:
        name = t.value
        if name in curr_module.dep_module_set:
            module = cocc_module.module_map[name]
            token_list.pop_sym(".")
            t, name = token_list.pop_name()
            if module.has_type_or_typedef(name):
                tp = _Type((t, name), token_list, curr_module.dep_module_set, module.name)
                tp.check(curr_module)
                return tp
        else:
            for module in curr_module, cocc_module.builtins_module:
                if module.has_type_or_typedef(name):
                    tp = _Type((t, name), token_list, curr_module.dep_module_set, module.name)
                    tp.check(curr_module)
                    return tp

def try_parse_type(token_list, curr_module):
    revert_idx = token_list.i #���ڽ���ʧ��ʱ��ع�
    ret = _try_parse_type(token_list, curr_module)
    if ret is None:
        token_list.revert(revert_idx)
    return ret

def gen_type_from_cls(cls):
    assert not cls.gtp_name_list
    return _Type((_FakeNonReservedToken(cls.name), cls.name), None, None, module_name = cls.module.name)
