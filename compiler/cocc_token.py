#coding=gbk

"""
��ģ�����Ϊtoken�б�
"""

import os
import re
import math
import cocc_common

#���ڽ���token��������ʽ
_TOKEN_RE = re.compile(
    #������
    r"""(\d+\.?\d*[eE][+-]?\w+|""" +
    r"""\.\d+[eE][+-]?\w+|""" +
    r"""\d+\.\w*|""" +
    r"""\.\d\w*)|""" +
    #����
    r"""(!=|==|<<=|<<|<=|>>=|>>|>=|[-%^&*+|/]=|&&|\|\||\+\+|--|\W)|""" +
    #����
    r"""(\d\w*)|""" +
    #�ʣ��ؼ��ֻ��ʶ��
    r"""([a-zA-Z_]\w*)""")

ASSIGN_SYM_SET = set(["=", "%=", "^=", "&=", "*=", "-=", "+=", "|=", "/=", "<<=", ">>="])
INC_DEC_SYM_SET = set(["++", "--"])
BINOCULAR_OP_SYM_SET = set(["%", "^", "&", "*", "-", "+", "|", "<", ">", "/", "!=", "==", "<<", "<=", ">>", ">=", "&&", "||"])

#�Ϸ��ķ��ż�
_SYM_SET = set("""~!%^&*()-+|{}[]:;"'<,>.?/""") | set(["!=", "==", "<<", "<=", ">>", ">=", "&&", "||"]) | ASSIGN_SYM_SET | INC_DEC_SYM_SET

#�����ּ�
_RESERVED_WORD_SET = set(["import", "class", "void", "bool", "byte", "ubyte", "char", "short", "ushort", "int", "uint", "long", "ulong",
                          "float", "double", "ldouble", "for", "while", "do", "if", "else", "return", "null", "true", "false", "break",
                          "continue", "this", "super", "public", "protected", "private", "interface", "new", "final", "native", "ref", "is",
                          "typedef", "abstract"])

class _Token:
    def __init__(self, type, value, src_file, line_no, pos):
        self.type = type
        self.value = value
        self.src_file = src_file
        self.line_no = line_no
        self.pos = pos

        self._set_is_XXX()

    def _set_is_XXX(self):
        """���ø���is_XXX����
           ���ʵ��Ϊ���������ܻ���ż����������Ī������Ĵ��󣬱��磺if token.is_literal()д����if token.is_literal������bug
           ����ʵ��Ϊ���ԣ�����·��գ���literal��sym�ȴʷ�Ԫ�ص��ж�ʵ��Ϊ���������Զ����ԣ�����token.is_sym��token.is_sym(sym)�����Թ���"""

        class IsLiteral:
            def __init__(self, token):
                self.token = token
            def __nonzero__(self):
                return self.token.type.startswith("literal_")
            def __call__(self, type):
                assert type in ("null", "bool", "char", "int", "uint", "long", "ulong", "float", "double", "str")
                return self and self.token.type == "literal_" + type
        self.is_literal = IsLiteral(self)

        class IsSym:
            def __init__(self, token):
                self.token = token
            def __nonzero__(self):
                return self.token.type == "sym"
            def __call__(self, sym):
                assert sym in _SYM_SET
                return self and self.token.value == sym
        self.is_sym = IsSym(self)

        class IsReserved:
            def __init__(self, token):
                self.token = token
            def __nonzero__(self):
                return self.token.type == "word" and self.token.value in _RESERVED_WORD_SET
            def __call__(self, word):
                assert word in _RESERVED_WORD_SET, str(word)
                return self and self.token.value == word
        self.is_reserved = IsReserved(self)
        self.is_name = self.type == "word" and self.value not in _RESERVED_WORD_SET

    def __str__(self):
        return """<token %r, %d, %d, %r>""" % (self.src_file, self.line_no, self.pos + 1, self.value)

    def __repr__(self):
        return self.__str__()

    def syntax_err(self, msg = ""):
        cocc_common.exit("�﷨�����ļ�[%s]��[%d]��[%d]%s" % (self.src_file, self.line_no, self.pos + 1, msg))

class TokenList:
    def __init__(self, src_file):
        self.src_file = src_file
        self.l = []
        self.i = 0

    def __nonzero__(self):
        return self.i < len(self.l)

    def peek(self):
        if not self:
            cocc_common.exit("�﷨�����ļ�[%s]�����������" % self.src_file)
        return self.l[self.i]

    def peek_name(self):
        t = self.peek()
        if not t.is_name:
            t.syntax_err("��Ҫ��ʶ��")
        return t.value

    def revert(self, i = None):
        if i is None:
            assert self.i > 0
            self.i -= 1
        else:
            assert 0 <= i < len(self.l)
            self.i = i

    def pop(self):
        t = self.peek()
        self.i += 1
        return t

    def pop_sym(self, sym = None):
        t = self.pop()
        if not t.is_sym:
            if sym is None:
                t.syntax_err("��Ҫ����")
            else:
                t.syntax_err("��Ҫ����'%s'" % sym)
        if sym is None:
            return t, t.value
        if t.value != sym:
            t.syntax_err("��Ҫ'%s'" % sym)

    def pop_name(self):
        t = self.pop()
        if not t.is_name:
            t.syntax_err("��Ҫ��ʶ��")
        return t, t.value

    def append(self, t):
        assert isinstance(t, _Token)
        self.l.append(t)

    def _remove_None(self):
        self.l = [t for t in self.l if t is not None]

    def join_str_literal(self):
        #�ϲ�ͬ���ʽ�����ڵ��ַ�������"abc""def""123"�ϲ�Ϊ"abcdef123"
        first = None
        for i, t in enumerate(self.l):
            if first is not None:
                #���ںϲ�
                if t.type == first.type:
                    first.value += t.value
                    self.l[i] = None
                else:
                    #����token����������
                    first = None
            elif t.is_literal("str"):
                #��ʼ����
                first = t
        self._remove_None()

    def split_shr_sym(self):
        assert self.i > 0
        t = self.l[self.i - 1]
        assert t.is_sym(">>")
        self.l[self.i - 1] = _Token("sym", ">", t.src_file, t.line_no, t.pos)
        self.l.insert(self.i, _Token("sym", ">", t.src_file, t.line_no, t.pos + 1))

def _syntax_err(src_file, line_no, pos, msg):
    cocc_common.exit("�﷨�����ļ�[%s]��[%d]��[%d]%s" % (src_file, line_no, pos + 1, msg))

def _get_escape_char(s, src_file, line_no, pos):
    if s[0] in "abfnrtv":
        #�������ת��
        return eval("'\\" + s[0] + "'"), s[1 :]

    if s[0] in ("\\", "'", '"'):
        #б�ܺ�����ת��
        return s[0], s[1 :]

    if s[0] >= "0" and s[0] <= "7":
        #�˽��ƻ������У�1��3λ����
        for k in s[: 3], s[: 2], s[0]:
            try:
                i = int(k, 8)
                break
            except ValueError:
                pass
        if i > 255:
            _syntax_err(src_file, line_no, pos, "�˽��ƻ�������ֵ����[\\%s]" % k)
        return chr(i), s[len(k) :]

    if s[0] == "x":
        #ʮ�����ƻ������У���λHH
        if len(s) < 3:
            _syntax_err(src_file, line_no, pos, "ʮ�����ƻ������г��Ȳ���")
        try:
            i = int(s[1 : 3], 16)
        except ValueError:
            _syntax_err(src_file, line_no, pos, "ʮ�����ƻ�������ֵ����[\\%s]" % s[: 3])
        return chr(i), s[3 :]

    _syntax_err(src_file, line_no, pos, "�Ƿ���ת���ַ�[%s]" % s[0])

def _parse_str(s, src_file, line_no, pos):
    #���������е��ַ���
    s_len = len(s)
    quota = s[0]
    s = s[1 :]

    l = [] #�ַ��б�

    while s:
        c = s[0]
        s = s[1 :]
        if c == quota:
            break
        if c == "\\":
            #ת���ַ�
            if s == "":
                _syntax_err(src_file, line_no, pos, "�ַ�����ת�崦����")
            c, s = _get_escape_char(s, src_file, line_no, pos)
        else:
            #��ͨ�ַ�
            if ord(c) < 32:
                _syntax_err(src_file, line_no, pos, "�ַ����г���ascii������[0x%02X]" % ord(c))
        l.append(c) #��ӵ��б�
    else:
        _syntax_err(src_file, line_no, pos, "�ַ���������")

    #���������������ĵ�Դ���볤��
    return "".join(l), s_len - len(s)

def _parse_token(src_file, line_no, line, pos):
    s = line[pos :]
    m = _TOKEN_RE.match(s)
    if m is None:
        _syntax_err(src_file, line_no, pos, "")

    f, sym, i, w = m.groups()

    if f is not None:
        #������
        if f[-1] == "F":
            try:
                value = float(f[: -1])
                if math.isnan(value) or math.isinf(value):
                    raise ValueError
                if value < float.fromhex("0x1p-126"):
                    value = 0
                elif value > float.fromhex("0x1.FFFFFEp127"):
                    raise ValueError
            except ValueError:
                _syntax_err(src_file, line_no, pos, "�Ƿ���float������'%s'" % f)
            return _Token("literal_float", value, src_file, line_no, pos), len(f)
        else:
            try:
                value = float(f)
                if math.isnan(value) or math.isinf(value):
                    raise ValueError
            except ValueError:
                _syntax_err(src_file, line_no, pos, "�Ƿ���double������'%s'" % f)
            return _Token("literal_double", value, src_file, line_no, pos), len(f)

    if sym is not None:
        #����
        if sym not in _SYM_SET:
            _syntax_err(src_file, line_no, pos, "�Ƿ��ķ���'%s'" % sym)

        if sym in ("'", '"'):
            #�ַ����ַ���
            value, token_len = _parse_str(s, src_file, line_no, pos)
            if sym == '"':
                #�ַ���
                return _Token("literal_str", value, src_file, line_no, pos), token_len
            #�ַ�
            if len(value) != 1:
                _syntax_err(src_file, line_no, pos, "�ַ����������ȱ���Ϊ1")
            return _Token("literal_char", ord(value), src_file, line_no, pos), token_len

        #��ͨ����token
        return _Token("sym", sym, src_file, line_no, pos), len(sym)

    if i is not None:
        #����
        try:
            if i[-2 :] == "UL":
                value = int(i[: -2], 0)
                if value >= 2 ** 64:
                    _syntax_err(src_file, line_no, pos, "�����ulong������'%s'" % i)
                type = "ulong"
            elif i[-1] == "L":
                value = int(i[: -1], 0)
                if value >= 2 ** 63:
                    _syntax_err(src_file, line_no, pos, "�����long������'%s'" % i)
                type = "long"
            elif i[-1] == "U":
                value = int(i[: -1], 0)
                if value >= 2 ** 32:
                    _syntax_err(src_file, line_no, pos, "�����uint������'%s'" % i)
                type = "uint"
            else:
                value = int(i, 0)
                if value >= 2 ** 31:
                    _syntax_err(src_file, line_no, pos, "�����int������'%s'" % i)
                type = "int"
        except ValueError:
            _syntax_err(src_file, line_no, pos, "�Ƿ�������������'%s'" % i)
        return _Token("literal_" + type, value, src_file, line_no, pos), len(i)

    if w is not None:
        if w in ("true", "false"):
            return _Token("literal_bool", w, src_file, line_no, pos), len(w)
        if w == "null":
            return _Token("literal_null", w, src_file, line_no, pos), len(w)
        return _Token("word", w, src_file, line_no, pos), len(w)

    raise Exception("bug")

def parse_token_list(src_file):
    f = open(src_file)
    f.seek(0, os.SEEK_END)
    if f.tell() > 100 * 1024 ** 2:
        cocc_common.exit("Դ�����ļ�[%s]����" % src_file)
    f.seek(0, os.SEEK_SET)
    line_list = f.read().splitlines()

    token_list = TokenList(src_file)
    in_comment = False
    for line_no, line in enumerate(line_list):
        line_no += 1

        if in_comment:
            #��δ���ע��
            pos = line.find("*/")
            if pos < 0:
                #���ж���ע�ͣ�����
                continue
            pos += 2
            in_comment = False
        else:
            pos = 0

        #������ǰ��token
        while pos < len(line):
            #�����ո�
            while pos < len(line) and line[pos] in "\t\x20":
                pos += 1
            if pos >= len(line):
                #�н���
                break

            if line[pos : pos + 2] == "//":
                #����ע�ͣ��Թ�����
                break
            if line[pos : pos + 2] == "/*":
                #��ע��
                pos += 2
                comment_end_pos = line[pos :].find("*/")
                if comment_end_pos < 0:
                    #ע�Ϳ����ˣ����ñ���Թ�����
                    in_comment = True
                    break
                #ע���ڱ��н�����������
                pos += comment_end_pos + 2
                continue

            #����token
            token, token_len = _parse_token(src_file, line_no, line, pos)
            token_list.append(token)
            pos += token_len

    if in_comment:
        _syntax_err(src_file, len(line_list), len(line_list[-1]), "����δ�����Ŀ�ע��")

    token_list.join_str_literal()

    return token_list
