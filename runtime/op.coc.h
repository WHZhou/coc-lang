#ifndef OP_COC_H
#define OP_COC_H

//���ļ�ͳһ������util.coc.h���Ͳ����԰�����

template <typename T>
void inc_coc_obj(T &num)
{
    ++ num;
}
template <typename T>
void inc_coc_obj(CocPtr<T> &coc_ptr)
{
    coc_ptr.method___op_inc();
}

#endif
