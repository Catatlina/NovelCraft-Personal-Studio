#!/usr/bin/env python3
"""
第一期集成测试脚本

测试内容：
1. 封神品类验证（世界观硬约束）
2. 去AI味两层验证（词级 + 模式级）
3. 各模块交叉验证（钩力、角色平衡、金句、读者模拟）
4. 性能测试（各模块耗时）
"""

import sys
import time
sys.path.insert(0, 'backend/app/v7/quality')

from world_constraint import get_constraint_pack, list_available_packs
from structural_ai_smell import analyze_structural_ai_smell
from reader_simulation import simulate_reader_first_pass
from hook_analysis import analyze_hook_power
from character_balance import analyze_character_balance
from golden_quote_detector import detect_golden_quotes


def test_world_constraint():
    """测试1：封神品类验证"""
    print("=" * 60)
    print("测试1：封神世界观硬约束验证")
    print("=" * 60)
    
    # 1.1 测试违规文本
    print("\n1.1 违规文本测试（应该检测出违规）")
    print("-" * 40)
    
    bad_text = """
    主角修炼到了筑基期，马上就要突破金丹期了。
    他的灵根是极品天灵根，天赋异禀。
    身上带着储物袋，里面装满了灵石和丹药。
    还有一枚储物戒指，是他师父留给他的。
    作为一个修仙者，他的目标是飞升成仙。
    """
    
    pack = get_constraint_pack("fengshen")
    result = pack.check_text(bad_text)
    
    print(f"总违规数: {result['summary']['total_violations']}")
    print(f"高级违规: {result['summary']['high_severity']}")
    print(f"中级违规: {result['summary']['medium_severity']}")
    print(f"低级违规: {result['summary']['low_severity']}")
    print(f"是否通过: {result['passed']}")
    
    print("\n违规详情:")
    for violation in result['violations'][:5]:
        print(f"  [{violation['severity']}] {violation['rule_id']}: {violation['description']}")
        print(f"    命中: {violation['matched']}")
    
    # 1.2 测试正常文本
    print("\n1.2 正常封神文本测试（应该无违规）")
    print("-" * 40)
    
    good_text = """
    姜子牙站在封神台上，手持打神鞭。
    他是阐教弟子，奉元始天尊之命下山封神。
    炼气士们纷纷前来，有的是来投奔的，有的是来挑战的。
    这是一个仙凡共存的时代，人神妖混居。
    """
    
    result2 = pack.check_text(good_text)
    
    print(f"总违规数: {result2['summary']['total_violations']}")
    print(f"是否通过: {result2['passed']}")
    
    # 1.3 测试可用约束包列表
    print("\n1.3 可用约束包列表")
    print("-" * 40)
    packs = list_available_packs()
    print(f"可用约束包: {packs}")
    
    print("\n✅ 封神世界观硬约束测试完成\n")
    return result['summary']['total_violations'] > 0 and result2['summary']['total_violations'] == 0


def test_deai_two_layer():
    """测试2：去AI味两层验证"""
    print("=" * 60)
    print("测试2：去AI味两层验证（词级 + 模式级）")
    print("=" * 60)
    
    # 2.1 测试AI味重的文本
    print("\n2.1 AI味重的文本测试（应该检测出问题）")
    print("-" * 40)
    
    ai_text = """
    然而，他深深地知道，这一切都只是开始。
    但是，他并没有放弃，而是默默地继续努力着。
    缓缓地，他抬起头，静静地看着远方。
    轻轻地，他叹了口气，心中充满了感慨。
    
    他知道，人生就像一场旅行，重要的不是目的地，而是沿途的风景。
    他明白，只有经历过风雨，才能见到彩虹。
    总而言之，这是一段难忘的经历。
    由此可见，坚持就是胜利。
    
    然而，事情并没有那么简单。
    但是，他相信自己一定能够成功。
    从此，他的人生发生了翻天覆地的变化。
    也许这就是命运吧。
    """
    
    result = analyze_structural_ai_smell(ai_text, threshold_preset="tomato")
    
    print(f"总体评分: {result.overall_score}/100 ({result.grade})")
    print(f"是否通过: {result.passed}")
    print(f"通过维度: {sum(1 for d in result.dimensions if d.passed)}/{len(result.dimensions)}")
    
    print("\n各维度详情:")
    for dim in result.dimensions:
        status = "✅" if dim.passed else "❌"
        print(f"  {status} {dim.name}: {dim.score:.1f}/100 (实际: {dim.actual:.2f}{dim.unit}, 阈值: {dim.threshold}{dim.unit})")
    
    # 2.2 测试正常网文文本
    print("\n2.2 正常网文文本测试（应该大部分通过）")
    print("-" * 40)
    
    normal_text = """
    林越推开门，走了进去。
    屋里很黑，什么都看不见。
    "有人吗？"他喊了一声。
    没人回答。
    
    他摸索着往前走，脚下突然踢到了什么东西。
    低头一看，是一个箱子。
    打开箱子，里面全是钱。
    林越愣住了。
    
    这是怎么回事？
    谁把钱放在这里的？
    他环顾四周，一个人都没有。
    就在这时，身后传来了脚步声。
    """
    
    result2 = analyze_structural_ai_smell(normal_text, threshold_preset="tomato")
    
    print(f"总体评分: {result2.overall_score}/100 ({result2.grade})")
    print(f"是否通过: {result2.passed}")
    print(f"通过维度: {sum(1 for d in result2.dimensions if d.passed)}/{len(result2.dimensions)}")
    
    print("\n✅ 去AI味两层验证测试完成\n")
    return not result.passed and result2.overall_score > result.overall_score


def test_hook_analysis():
    """测试3：首章钩力分析"""
    print("=" * 60)
    print("测试3：首章钩力分析验证")
    print("=" * 60)
    
    test_text = """
    「林越，你被开除了。」
    
    经理把辞退报告拍在桌上，脸上满是不屑。
    
    林越愣住了。
    
    「为什么？」
    
    「为什么？」经理冷笑一声，「你自己干了什么好事，心里没数吗？」
    
    林越握紧了拳头。
    
    他没有！
    
    就在这时——
    
    【叮！神豪系统正在绑定宿主……】
    
    【绑定成功！】
    
    林越笑了。
    
    他抬起头，看着眼前的经理，嘴角勾起一抹冷笑。
    
    「你刚才说什么？让我走人？」
    
    「我说，你被开除了。」
    
    林越摇了摇头。
    
    「不，是你被开除了。」
    """
    
    result = analyze_hook_power(test_text, 'fanqie')
    
    print(f"总体评分: {result['overall_score']} 分 ({result['grade']}级)")
    print(f"章节长度: {result['chapter_length']} 字")
    print(f"预估留存率: {result['estimated_retention']['retention_rate']}%")
    
    print("\n6个维度:")
    print(f"  1. 开篇钩子: {result['opening_hook']['score']}/10 - {result['opening_hook']['comment']}")
    print(f"  2. 爽点位置: 第{result['first_payoff']['position']}字 - {result['first_payoff']['comment']}")
    print(f"  3. 章末钩子: {result['ending_hook']['score']}/10 - {result['ending_hook']['comment']}")
    print(f"  4. 信息节奏: {result['information_release']['score']}/10 - {result['information_release']['comment']}")
    print(f"  5. 人物辨识: {result['character_recognition']['score']}/10 - {result['character_recognition']['comment']}")
    print(f"  6. 预估留存: {result['estimated_retention']['retention_rate']}%")
    
    if result['suggestions']:
        print("\n改进建议:")
        for i, s in enumerate(result['suggestions'], 1):
            print(f"  {i}. {s}")
    
    print("\n✅ 首章钩力分析测试完成\n")
    return result['overall_score'] > 0


def test_character_balance():
    """测试4：角色出场平衡检查"""
    print("=" * 60)
    print("测试4：角色出场平衡检查验证")
    print("=" * 60)
    
    # 构造10章文本
    chapters = []
    
    # 第1-5章：所有角色都出场
    for i in range(5):
        chapter = f"""
        第{i+1}章
        
        林越走在街上。
        苏小雨从后面跑了过来。
        王浩走了过来，脸上带着不屑。
        赵大爷从旁边走过，叹了口气。
        """
        chapters.append(chapter)
    
    # 第6-8章：只有林越和苏小雨出场
    for i in range(3):
        chapter = f"""
        第{i+6}章
        
        林越和苏小雨一起去了公园。
        他们在公园里散步，聊了很多事情。
        """
        chapters.append(chapter)
    
    # 第9-10章：只有林越出场
    for i in range(2):
        chapter = f"""
        第{i+9}章
        
        林越一个人在家，看着窗外的风景。
        他想起了很多事情。
        """
        chapters.append(chapter)
    
    character_list = ['林越', '苏小雨', '王浩', '赵大爷']
    result = analyze_character_balance(chapters, character_list)
    
    print(f"总角色数: {result.total_characters}")
    print(f"总章节数: {result.total_chapters}")
    print(f"平衡评分: {result.balance_score}/100")
    print(f"是否有警告: {'是' if result.has_warnings else '否'}")
    
    print(f"\n高风险角色: {len(result.high_risk_characters)} 个")
    print(f"中风险角色: {len(result.medium_risk_characters)} 个")
    print(f"低风险角色: {len(result.low_risk_characters)} 个")
    
    if result.medium_risk_characters:
        print("\n中风险角色详情:")
        for stats in result.medium_risk_characters:
            print(f"  - {stats.name}: {stats.chapters_since_last}章没出场 (重要性: {stats.importance})")
    
    if result.suggestions:
        print("\n改进建议:")
        for i, s in enumerate(result.suggestions, 1):
            print(f"  {i}. {s}")
    
    print("\n✅ 角色出场平衡测试完成\n")
    return result.balance_score < 100 and len(result.medium_risk_characters) > 0


def test_golden_quote():
    """测试5：金句检测"""
    print("=" * 60)
    print("测试5：金句检测验证")
    print("=" * 60)
    
    test_text = """
    林越站在窗前，看着外面的雨。
    
    以前记是因为习惯。现在记，是因为命。
    
    命运从来都不是公平的。但我们可以选择怎么活。
    
    没有退路，只能前进。
    
    绝不认输。永远绝不。
    
    「因为这就是我。」林越淡淡地说。
    """
    
    result = detect_golden_quotes(test_text, max_quotes=5, min_score=10)
    
    print(f"章节长度: {result.chapter_length} 字")
    print(f"候选金句数: {result.total_count}")
    print(f"是否有高质量金句: {'是' if result.has_high_quality else '否'}")
    
    if result.best_quote:
        print(f"\n最佳金句: 「{result.best_quote.text}」")
        print(f"  评分: {result.best_quote.score}/100")
        print(f"  类型: {result.best_quote.quote_type}")
    
    print("\n所有候选金句:")
    for i, quote in enumerate(result.quotes, 1):
        print(f"  {i}. 「{quote.text}」({quote.score:.1f}分, {quote.quote_type})")
    
    if result.suggestions:
        print("\n改进建议:")
        for i, s in enumerate(result.suggestions, 1):
            print(f"  {i}. {s}")
    
    print("\n✅ 金句检测测试完成\n")
    return result.total_count > 0


def test_reader_simulation():
    """测试6：读者模拟审查框架"""
    print("=" * 60)
    print("测试6：读者模拟审查框架验证")
    print("=" * 60)
    
    test_text = """
    「林越，你被开除了。」
    
    经理把辞退报告拍在桌上，脸上满是不屑。
    
    林越愣住了。
    
    【叮！神豪系统正在绑定宿主……】
    
    【绑定成功！】
    
    林越笑了。
    
    「你被开除了。」
    """
    
    result = simulate_reader_first_pass(test_text, 'fanqie')
    
    print(f"读者画像: {result['reader_persona']}")
    print(f"文本长度: {result['text_length']} 字")
    print(f"说明: {result['note']}")
    
    if 'result' in result:
        r = result['result']
        print(f"\n总体评分: {r.get('overall_score', 'N/A')}")
        print(f"开篇钩子: {r.get('opening_hook_score', 'N/A')}/10")
        print(f"追读意愿: {r.get('continuation_intent_score', 'N/A')}/10")
    
    print("\n✅ 读者模拟审查框架测试完成\n")
    return True  # 框架正常返回即可


def test_performance():
    """测试7：性能测试"""
    print("=" * 60)
    print("测试7：性能测试（各模块耗时）")
    print("=" * 60)
    
    # 构造一个较长的测试文本（约3000字）
    long_text = ""
    for i in range(100):
        long_text += f"这是第{i+1}句话，用来测试性能的。"
        if i % 5 == 0:
            long_text += "\n\n"
    
    print(f"测试文本长度: {len(long_text)} 字符\n")
    
    # 测试世界观约束
    start = time.time()
    pack = get_constraint_pack("fengshen")
    pack.check_text(long_text)
    wc_time = time.time() - start
    print(f"世界观约束: {wc_time*1000:.2f} ms")
    
    # 测试模式级AI味检测
    start = time.time()
    analyze_structural_ai_smell(long_text, "tomato")
    ai_time = time.time() - start
    print(f"模式级AI味检测: {ai_time*1000:.2f} ms")
    
    # 测试首章钩力分析
    start = time.time()
    analyze_hook_power(long_text, "fanqie")
    hook_time = time.time() - start
    print(f"首章钩力分析: {hook_time*1000:.2f} ms")
    
    # 测试金句检测
    start = time.time()
    detect_golden_quotes(long_text)
    quote_time = time.time() - start
    print(f"金句检测: {quote_time*1000:.2f} ms")
    
    # 测试角色平衡（10章）
    chapters = [long_text] * 10
    start = time.time()
    analyze_character_balance(chapters, ['角色1', '角色2', '角色3'])
    char_time = time.time() - start
    print(f"角色平衡检查(10章): {char_time*1000:.2f} ms")
    
    total = wc_time + ai_time + hook_time + quote_time
    print(f"\n单章总耗时(不含角色平衡): {total*1000:.2f} ms")
    print(f"性能评估: {'✅ 优秀' if total < 0.1 else '⚠️ 可接受' if total < 0.5 else '❌ 需优化'}")
    
    print("\n✅ 性能测试完成\n")
    return total < 1.0  # 总耗时小于1秒就算合格


def main():
    print("\n" + "=" * 60)
    print("NovelCraft 第一期集成测试")
    print("=" * 60 + "\n")
    
    results = {}
    
    # 运行所有测试
    results['world_constraint'] = test_world_constraint()
    results['deai_two_layer'] = test_deai_two_layer()
    results['hook_analysis'] = test_hook_analysis()
    results['character_balance'] = test_character_balance()
    results['golden_quote'] = test_golden_quote()
    results['reader_simulation'] = test_reader_simulation()
    results['performance'] = test_performance()
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    test_names = {
        'world_constraint': '封神世界观硬约束',
        'deai_two_layer': '去AI味两层验证',
        'hook_analysis': '首章钩力分析',
        'character_balance': '角色出场平衡',
        'golden_quote': '金句检测',
        'reader_simulation': '读者模拟审查',
        'performance': '性能测试',
    }
    
    passed = 0
    total = len(results)
    
    for key, name in test_names.items():
        status = "✅ 通过" if results.get(key, False) else "❌ 失败"
        print(f"  {status} - {name}")
        if results.get(key, False):
            passed += 1
    
    print(f"\n总计: {passed}/{total} 项通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！第一期集成测试成功！")
    else:
        print(f"\n⚠️  有 {total - passed} 项测试未通过，需要检查")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
