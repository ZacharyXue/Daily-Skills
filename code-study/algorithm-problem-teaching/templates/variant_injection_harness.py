"""单 bug 变体注入对拍骨架 —— 给每个 bug 单独算「它值多少失败率」

适用场景：用户贴来 N 个写法各异的版本（或你自己想量化「每个 bug 各有多致命」）。
做法：把算法写成 build(mode) 工厂，mode 决定注入哪个变体；变体之间只差一处，
      和 brute() 对拍，输出每个变体的失败数 + 最小反例。

关键约束
--------
* 变体之间**只差一处** —— 否则失败率变化归因不清，讲不出「这层 bug 值多少」。
* 死循环护栏用**步数计数器**，不要用 signal.setitimer 逐用例设闹钟：
  大量死循环用例时每个都吃满超时，几千用例能把工具调用拖过 300s（实测踩过）。
* oracle（brute）先自检：统计口径要和被讨论的量一致；有重复值时注意 bisect 语义。
* 失败率出现 50%+ 这种离谱数字时，先怀疑自己的度量口径，再怀疑被测代码。

用法：把 build() / brute() 换成你的题目，然后 python3 variant_injection_harness.py
"""

import random


class Timeout(Exception):
    """步数失控 / 死循环"""


# ---------------------------------------------------------------- 参考解（oracle）
def brute(a, b):
    """朴素暴力参考解。示例：合并取中位数。换题时替换这里。"""
    c = sorted(a + b)
    L = len(c)
    if L == 0:
        raise ValueError("空输入：先确认题目是否保证非空，再决定要不要用这个用例")
    return float(c[L // 2]) if L % 2 else (c[L // 2 - 1] + c[L // 2]) / 2


# ---------------------------------------------------------------- 被测算法工厂
def build(mode):
    """返回一个含指定变体的实现。mode="ok" 为正确版，其余各注入一处 bug。"""

    class S:
        def solve(self, nums1, nums2):
            m, n = len(nums1), len(nums2)

            def kth(k):
                i = j = 0
                steps = 0
                while True:
                    steps += 1
                    if steps > 200:                 # ← 死循环护栏，必须有
                        raise Timeout("步数失控")
                    # ---- 边界：任一数组耗尽 / k 归 1 ----
                    if i >= m:
                        return nums2[j + k - 1]
                    if j >= n:
                        return nums1[i + k - 1]
                    if k == 1:
                        return min(nums1[i], nums2[j])
                    # ---- 正常轮：看哪 / 扔几个 / 减多少 ----
                    c1 = min(m - 1, i + k // 2 - 1)
                    c2 = min(n - 1, j + k // 2 - 1)
                    if nums1[c1] <= nums2[c2]:
                        take1 = True
                    else:
                        take1 = False

                    if mode == "head":                  # 变体：比「队首」而非 pivot
                        take1 = nums1[i] < nums2[j]

                    if take1:
                        removed = c1 - i + 1
                        if mode == "plan":              # 变体：k -= k//2（按计划减，非实际）
                            removed = k // 2
                        elif mode == "nocount":         # 变体：闭区间漏算 curr 自己
                            removed = c1 - i
                        k -= removed
                        i = c1 + 1
                    else:
                        removed = c2 - j + 1
                        if mode == "plan":
                            removed = k // 2
                        elif mode == "nocount":
                            removed = c2 - j
                        k -= removed
                        j = c2 + 1

            if (m + n) % 2:
                return float(kth((m + n + 1) // 2))
            return (kth((m + n) // 2) + kth((m + n) // 2 + 1)) / 2

    return S()


# ---------------------------------------------------------------- 对拍
MODES = [
    ("ok", "✅ 正确版"),
    ("head", "变体：比队首而非 pivot"),
    ("plan", "变体：k -= k//2（按计划减）"),
    ("nocount", "变体：闭区间漏算 curr 自己"),
]


def make_cases(n_random=4000, lo=0, hi=9, vlo=-5, vhi=30, seed=2026):
    """随机小规模 + 手工边界。小规模 + 窄值域能提高边界碰撞率。"""
    random.seed(seed)
    cases = [
        ([], [1]), ([1], []), ([1], [2]), ([1, 3], [2]), ([1, 2], [3, 4]),
        ([1], [2, 3, 4, 5, 6, 7]),          # 长度悬殊：最容易打到边界夹取
        ([1, 100, 101], [2, 3, 4]),          # 判据陷阱：队首小但段内最大者大
        ([0, 0], [0, 0]),                    # 全相等：暴露索引笔误 / 重复值
        ([1, 2, 3, 4, 5], [6]),
    ]
    for _ in range(n_random):
        m, n = random.randint(lo, hi), random.randint(lo, hi)
        if m + n == 0:
            continue
        cases.append((sorted(random.randint(vlo, vhi) for _ in range(m)),
                      sorted(random.randint(vlo, vhi) for _ in range(n))))
    return cases


def check(impl, name, cases, show=4):
    fails = []
    for a, b in cases:
        try:
            got = impl.solve(a, b)
        except Exception as e:
            got = f"{type(e).__name__}"
        exp = brute(a, b)
        if got != exp:
            fails.append((a, b, exp, got))
    print(f"\n=== {name} ===  失败 {len(fails)}/{len(cases)}")
    for a, b, exp, got in fails[:show]:
        print(f"    nums1={a} nums2={b} 期望={exp} 实际={got}")
    return fails


if __name__ == "__main__":
    cases = make_cases()
    for mode, label in MODES:
        check(build(mode), label, cases)
    print("\n解读：跑几组变体后，再用单 bug 变体定量「这层 bug 值多少失败率」，"
          "讲解时直接引用数字，比「我觉得这里有问题」有力一个量级。")
