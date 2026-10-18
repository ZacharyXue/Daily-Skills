"""算法题对拍骨架（algorithm-problem-teaching / 子模式 B）

用法：
    mkdir -p /tmp/lc<N> && cp templates/diff_test_harness.py /tmp/lc<N>/test.py
    把 V1/V2/... 换成用户提交的版本，改 brute() 与 gen_cases()，然后 python3 test.py

要点：
  ① 参考解用最朴素的暴力（能一遍看懂、不可能错的那种）；
  ② 随机用例规模要小、值域要窄 —— 边界碰撞率高才抓得到 bug；
  ③ 手工边界用例单独列（空集合 / 单元素 / 长度悬殊 / 全相等）；
  ④ 必须带死循环护栏 —— **首选在待测代码的 while 入口加步数计数上限**（见下方 GUARD 片段）。
     别靠 signal.setitimer 逐用例设闹钟：死循环用例每个都吃满闹钟时长，
     实测 0.3s × 1344 个死循环用例 → 对拍跑过 300s 工具超时、白跑一轮。setitimer 只留 1s 粗兜底；
  ⑤ 先跑 Ref() 自检：参考解本身必须 0 失败，否则是 harness 写错了。
"""
import random
import signal


class Timeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise Timeout("超时/死循环")


signal.signal(signal.SIGALRM, _on_alarm)

# ============ GUARD：死循环护栏首选方案 ============
# 在被测代码的 while 入口插入（纯整数计数，开销可忽略）：
#
#     def getKthElement(k):
#         steps = 0
#         while True:
#             steps += 1
#             if steps > STEP_LIMIT:
#                 raise Timeout("步数失控")
#             ...
#
# k 归零 / 指针倒退类 bug 会被这里抓住；比 setitimer 快数百倍。
STEP_LIMIT = 200


# ============ 1. 参考解：最朴素的暴力实现 ============
def brute(a, b):
    c = sorted(a + b)
    L = len(c)
    return float(c[L // 2]) if L % 2 else (c[L // 2 - 1] + c[L // 2]) / 2


# ============ 2. 待测版本：原样抄用户代码，别顺手「修好」 ============
class V1:
    def findMedianSortedArrays(self, nums1, nums2):
        ...  # 用户最新提交


class V2:
    def findMedianSortedArrays(self, nums1, nums2):
        ...  # 用户上一版


class Ref:
    """正确实现，用于自检 harness"""

    def findMedianSortedArrays(self, nums1, nums2):
        ...


# ============ 3. 用例：手工边界 + 随机小规模 ============
MANUAL = [
    ([], [1]), ([1], []), ([1], [2]), ([1], [2, 3, 4, 5, 6, 7]), ([0, 0], [0, 0]),
]


def gen_cases(n=4000, seed=42, maxlen=9, lo=-5, hi=30):
    random.seed(seed)
    cases = list(MANUAL)
    for _ in range(n):
        m, k = random.randint(0, maxlen), random.randint(0, maxlen)
        if m + k == 0:  # 题目通常保证非空
            continue
        cases.append((sorted(random.randint(lo, hi) for _ in range(m)),
                      sorted(random.randint(lo, hi) for _ in range(k))))
    return cases


# ============ 4. 跑对拍：报失败率 + 最小反例 ============
def run(impl, name, cases, show=6):
    fails = []
    for a, b in cases:
        try:
            signal.setitimer(signal.ITIMER_REAL, 1.0)   # 粗兜底；主护栏是测码里的步数计数（见 GUARD）
            got = impl.findMedianSortedArrays(a, b)
        except Exception as e:
            got = f"{type(e).__name__}: {e}"
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        exp = brute(a, b)
        if got != exp:
            fails.append((a, b, exp, got))
    print(f"\n=== {name} === 失败 {len(fails)}/{len(cases)}")
    # 按用例长度排序 → 最短的即「最小反例」，讲解时直接用它
    for f in sorted(fails, key=lambda x: len(x[0]) + len(x[1]))[:show]:
        print(f"   nums1={f[0]} nums2={f[1]} 期望={f[2]} 实际={f[3]}")
    return fails


if __name__ == "__main__":
    cases = gen_cases()
    run(Ref(), "参考解自检（必须 0 失败）", cases)
    run(V1(), "版本1", cases)
    run(V2(), "版本2", cases)
