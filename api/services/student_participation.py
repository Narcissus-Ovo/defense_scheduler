"""Recognize explicit roster remarks; an empty campus alone proves nothing."""
import re


def nonparticipation_reason(remark):
    text = str(remark or '').strip()
    # Match complete declarations, never substrings such as 未转博/申请休学待审批.
    if re.fullmatch(r'(?:已)?(?:休学|转博|毕业|退学)|(?:在)?外院答辩(?:[（(][^）)]+[）)]|[-－—].+)?|(?:本次)?不参加答辩', text):
        return text
    return ''
