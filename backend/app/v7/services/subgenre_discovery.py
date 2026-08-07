"""
子品类自动发现模块

功能：
1. 无监督聚类，自动发现子品类（系统流/穿越流/重生流等）
2. 简化版 K-means 算法（纯 Python 实现，不依赖 sklearn）
3. 输出子品类地图、特征向量中心、代表作品、子品类描述
4. 离线计算，不影响在线生成
5. 支持肘部法则自动确定最优 K 值

使用方式：
    from app.v7.services.subgenre_discovery import discover_subgenres, kmeans_clustering

    # 聚类发现子品类
    result = discover_subgenres(features_list, k=5)
    print(result.clusters)  # 聚类结果
    print(result.cluster_centers)  # 聚类中心
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ============================================================
# 数据结构
# ============================================================

@dataclass
class SubgenreCluster:
    """子品类聚类结果。"""
    cluster_id: int  # 聚类ID
    name: str  # 子品类名称（自动生成）
    description: str  # 子品类描述
    center: List[float]  # 聚类中心（特征向量）
    sample_count: int  # 样本数量
    sample_indices: List[int]  # 样本索引列表
    representative_samples: List[int] = field(default_factory=list)  # 代表作品索引（离中心最近的）
    feature_importance: Dict[str, float] = field(default_factory=dict)  # 特征重要性（与其他聚类的差异）


@dataclass
class SubgenreDiscoveryResult:
    """子品类发现结果。"""
    clusters: List[SubgenreCluster]  # 聚类列表
    k: int  # 聚类数量
    iterations: int  # 迭代次数
    converged: bool  # 是否收敛
    total_samples: int  # 总样本数
    feature_names: List[str]  # 特征名称列表
    inertia: float = 0.0  # 簇内平方和（inertia）
    silhouette_score: float = 0.0  # 轮廓系数（可选）


# ============================================================
# 距离计算
# ============================================================

def euclidean_distance(v1: List[float], v2: List[float]) -> float:
    """计算欧氏距离。"""
    if len(v1) != len(v2):
        raise ValueError(f"向量长度不一致：{len(v1)} vs {len(v2)}")

    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """计算余弦相似度。"""
    if len(v1) != len(v2):
        raise ValueError(f"向量长度不一致：{len(v1)} vs {len(v2)}")

    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a ** 2 for a in v1))
    norm2 = math.sqrt(sum(b ** 2 for b in v2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def manhattan_distance(v1: List[float], v2: List[float]) -> float:
    """计算曼哈顿距离。"""
    if len(v1) != len(v2):
        raise ValueError(f"向量长度不一致：{len(v1)} vs {len(v2)}")

    return sum(abs(a - b) for a, b in zip(v1, v2))


# ============================================================
# 特征归一化
# ============================================================

def normalize_features(
    features: List[List[float]],
    method: str = "minmax",
) -> Tuple[List[List[float]], Dict]:
    """
    特征归一化。

    Args:
        features: 特征向量列表
        method: 归一化方法（minmax/zscore）

    Returns:
        (normalized_features, params)
    """
    if not features:
        return [], {}

    n_features = len(features[0])
    n_samples = len(features)

    if method == "minmax":
        # Min-Max 归一化到 [0, 1]
        mins = [min(f[i] for f in features) for i in range(n_features)]
        maxs = [max(f[i] for f in features) for i in range(n_features)]

        normalized = []
        for sample in features:
            norm_sample = []
            for i, val in enumerate(sample):
                if maxs[i] - mins[i] == 0:
                    norm_sample.append(0.5)
                else:
                    norm_sample.append((val - mins[i]) / (maxs[i] - mins[i]))
            normalized.append(norm_sample)

        params = {"method": "minmax", "mins": mins, "maxs": maxs}

    elif method == "zscore":
        # Z-Score 标准化
        means = [sum(f[i] for f in features) / n_samples for i in range(n_features)]
        stds = []
        for i in range(n_features):
            variance = sum((f[i] - means[i]) ** 2 for f in features) / n_samples
            stds.append(math.sqrt(variance))

        normalized = []
        for sample in features:
            norm_sample = []
            for i, val in enumerate(sample):
                if stds[i] == 0:
                    norm_sample.append(0.0)
                else:
                    norm_sample.append((val - means[i]) / stds[i])
            normalized.append(norm_sample)

        params = {"method": "zscore", "means": means, "stds": stds}

    else:
        raise ValueError(f"未知的归一化方法：{method}")

    return normalized, params


def denormalize_features(
    normalized: List[List[float]],
    params: Dict,
) -> List[List[float]]:
    """反归一化。"""
    if not normalized or not params:
        return normalized

    method = params.get("method", "minmax")
    n_features = len(normalized[0])

    if method == "minmax":
        mins = params["mins"]
        maxs = params["maxs"]
        denormalized = []
        for sample in normalized:
            denorm_sample = []
            for i, val in enumerate(sample):
                denorm_sample.append(val * (maxs[i] - mins[i]) + mins[i])
            denormalized.append(denorm_sample)

    elif method == "zscore":
        means = params["means"]
        stds = params["stds"]
        denormalized = []
        for sample in normalized:
            denorm_sample = []
            for i, val in enumerate(sample):
                denorm_sample.append(val * stds[i] + means[i])
            denormalized.append(denorm_sample)

    else:
        raise ValueError(f"未知的归一化方法：{method}")

    return denormalized


# ============================================================
# K-Means 聚类
# ============================================================

def kmeans_clustering(
    features: List[List[float]],
    k: int,
    max_iterations: int = 100,
    tolerance: float = 1e-4,
    distance_metric: str = "euclidean",
    random_state: Optional[int] = None,
) -> Tuple[List[int], List[List[float]], int, bool, float]:
    """
    K-Means 聚类算法（纯 Python 实现）。

    Args:
        features: 特征向量列表
        k: 聚类数量
        max_iterations: 最大迭代次数
        tolerance: 收敛阈值
        distance_metric: 距离度量（euclidean/cosine/manhattan）
        random_state: 随机种子

    Returns:
        (labels, centers, iterations, converged, inertia)
        - labels: 每个样本的聚类标签
        - centers: 聚类中心
        - iterations: 实际迭代次数
        - converged: 是否收敛
        - inertia: 簇内平方和
    """
    if not features:
        return [], [], 0, True, 0.0

    n_samples = len(features)
    n_features = len(features[0])

    if k <= 0:
        raise ValueError("k 必须大于 0")
    if k > n_samples:
        raise ValueError(f"k ({k}) 不能大于样本数 ({n_samples})")

    # 设置随机种子
    if random_state is not None:
        random.seed(random_state)

    # 距离函数
    if distance_metric == "euclidean":
        dist_func = euclidean_distance
    elif distance_metric == "cosine":
        dist_func = lambda a, b: 1 - cosine_similarity(a, b)
    elif distance_metric == "manhattan":
        dist_func = manhattan_distance
    else:
        raise ValueError(f"未知的距离度量：{distance_metric}")

    # 初始化中心点（K-Means++ 简化版）
    centers = _init_centers_kmeans_plusplus(features, k, dist_func, random_state)

    labels = [0] * n_samples
    iterations = 0
    converged = False

    for iteration in range(max_iterations):
        iterations = iteration + 1

        # 分配样本到最近的中心
        new_labels = []
        for sample in features:
            distances = [dist_func(sample, center) for center in centers]
            closest = distances.index(min(distances))
            new_labels.append(closest)

        # 检查是否收敛（标签没有变化）
        if new_labels == labels and iteration > 0:
            converged = True
            break

        labels = new_labels

        # 更新中心点
        new_centers = []
        for cluster_id in range(k):
            # 收集该聚类的所有样本
            cluster_samples = [
                features[i] for i in range(n_samples) if labels[i] == cluster_id
            ]

            if not cluster_samples:
                # 空聚类，随机重新初始化
                new_centers.append(features[random.randint(0, n_samples - 1)])
            else:
                # 计算均值
                center = []
                for j in range(n_features):
                    center.append(sum(s[j] for s in cluster_samples) / len(cluster_samples))
                new_centers.append(center)

        # 检查中心变化是否小于阈值
        center_shift = sum(
            dist_func(centers[i], new_centers[i]) for i in range(k)
        ) / k

        centers = new_centers

        if center_shift < tolerance:
            converged = True
            break

    # 计算 inertia（簇内平方和）
    inertia = 0.0
    for i, sample in enumerate(features):
        inertia += dist_func(sample, centers[labels[i]]) ** 2

    return labels, centers, iterations, converged, inertia


def _init_centers_kmeans_plusplus(
    features: List[List[float]],
    k: int,
    dist_func,
    random_state: Optional[int] = None,
) -> List[List[float]]:
    """
    K-Means++ 初始化中心点。

    选择第一个中心随机，后续中心选择离已有中心最远的点。
    """
    if random_state is not None:
        random.seed(random_state)

    n_samples = len(features)
    centers = []

    # 第一个中心随机选择
    first_idx = random.randint(0, n_samples - 1)
    centers.append(features[first_idx].copy())

    # 选择剩余的中心
    for _ in range(1, k):
        # 计算每个样本到最近中心的距离
        distances = []
        for sample in features:
            min_dist = min(dist_func(sample, center) for center in centers)
            distances.append(min_dist ** 2)

        # 按距离加权随机选择
        total = sum(distances)
        if total == 0:
            # 所有点都一样，随机选
            idx = random.randint(0, n_samples - 1)
        else:
            # 轮盘赌选择
            r = random.random() * total
            cumulative = 0
            idx = 0
            for i, d in enumerate(distances):
                cumulative += d
                if cumulative >= r:
                    idx = i
                    break

        centers.append(features[idx].copy())

    return centers


# ============================================================
# 肘部法则确定最优 K
# ============================================================

def find_optimal_k(
    features: List[List[float]],
    min_k: int = 2,
    max_k: int = 10,
    **kwargs,
) -> Tuple[int, List[float], List[float]]:
    """
    使用肘部法则确定最优 K 值。

    Args:
        features: 特征向量列表
        min_k: 最小 k 值
        max_k: 最大 k 值
        **kwargs: 传递给 kmeans_clustering 的参数

    Returns:
        (optimal_k, inertias, derivatives)
        - optimal_k: 最优 k 值
        - inertias: 每个 k 对应的 inertia
        - derivatives: 二阶导数（肘部位置）
    """
    inertias = []
    k_values = list(range(min_k, max_k + 1))

    for k in k_values:
        _, _, _, _, inertia = kmeans_clustering(features, k=k, **kwargs)
        inertias.append(inertia)

    # 计算二阶导数（找肘部）
    # 肘部是 inertia 下降最快的点之后的拐点
    if len(inertias) >= 3:
        # 一阶差分
        first_derivative = [
            inertias[i] - inertias[i + 1]
            for i in range(len(inertias) - 1)
        ]
        # 二阶差分
        second_derivative = [
            first_derivative[i] - first_derivative[i + 1]
            for i in range(len(first_derivative) - 1)
        ]

        # 最优 k 是二阶导数最大的位置 + 2（因为差分后索引偏移）
        if second_derivative:
            max_idx = second_derivative.index(max(second_derivative))
            optimal_k = k_values[max_idx + 2]
        else:
            optimal_k = k_values[0]
    else:
        optimal_k = k_values[0]
        second_derivative = []

    return optimal_k, inertias, second_derivative


# ============================================================
# 子品类发现
# ============================================================

def discover_subgenres(
    features: List[List[float]],
    feature_names: List[str],
    k: Optional[int] = None,
    min_k: int = 2,
    max_k: int = 8,
    auto_detect_k: bool = True,
    **kwargs,
) -> SubgenreDiscoveryResult:
    """
    发现子品类（聚类）。

    Args:
        features: 特征向量列表（每本小说一个向量）
        feature_names: 特征名称列表
        k: 聚类数量（如果为 None 且 auto_detect_k=True，则自动确定）
        min_k: 自动检测时的最小 k
        max_k: 自动检测时的最大 k
        auto_detect_k: 是否自动检测最优 k
        **kwargs: 传递给 kmeans_clustering 的参数

    Returns:
        SubgenreDiscoveryResult 发现结果
    """
    if not features:
        return SubgenreDiscoveryResult(
            clusters=[],
            k=0,
            iterations=0,
            converged=True,
            total_samples=0,
            feature_names=feature_names,
        )

    n_samples = len(features)
    n_features = len(features[0])

    # 归一化特征
    normalized_features, norm_params = normalize_features(features, method="minmax")

    # 确定 k 值
    if k is None and auto_detect_k:
        k, _, _ = find_optimal_k(
            normalized_features,
            min_k=min_k,
            max_k=min(max_k, n_samples - 1),
            **kwargs,
        )
    elif k is None:
        k = min(3, n_samples)

    k = min(k, n_samples)  # k 不能大于样本数

    # 执行 K-Means 聚类
    labels, centers_normalized, iterations, converged, inertia = kmeans_clustering(
        normalized_features,
        k=k,
        **kwargs,
    )

    # 反归一化中心点
    centers = denormalize_features(centers_normalized, norm_params)

    # 构建聚类结果
    clusters = []
    for cluster_id in range(k):
        # 收集该聚类的样本索引
        sample_indices = [i for i in range(n_samples) if labels[i] == cluster_id]
        sample_count = len(sample_indices)

        if sample_count == 0:
            continue

        # 找代表作品（离中心最近的 3 个）
        distances = []
        for idx in sample_indices:
            dist = euclidean_distance(normalized_features[idx], centers_normalized[cluster_id])
            distances.append((idx, dist))

        distances.sort(key=lambda x: x[1])
        representative_samples = [d[0] for d in distances[:3]]

        # 计算特征重要性（与全局均值的差异）
        global_center = [
            sum(f[i] for f in features) / n_samples
            for i in range(n_features)
        ]

        feature_importance = {}
        for i, name in enumerate(feature_names):
            if global_center[i] != 0:
                diff_pct = (centers[cluster_id][i] - global_center[i]) / abs(global_center[i]) * 100
            else:
                diff_pct = 0.0
            feature_importance[name] = round(diff_pct, 1)

        # 生成子品类名称和描述
        name, description = _generate_subgenre_description(
            cluster_id,
            centers[cluster_id],
            feature_names,
            feature_importance,
            sample_count,
        )

        cluster = SubgenreCluster(
            cluster_id=cluster_id,
            name=name,
            description=description,
            center=centers[cluster_id],
            sample_count=sample_count,
            sample_indices=sample_indices,
            representative_samples=representative_samples,
            feature_importance=feature_importance,
        )
        clusters.append(cluster)

    # 按样本数量排序
    clusters.sort(key=lambda c: c.sample_count, reverse=True)
    # 重新编号
    for i, cluster in enumerate(clusters):
        cluster.cluster_id = i

    return SubgenreDiscoveryResult(
        clusters=clusters,
        k=len(clusters),
        iterations=iterations,
        converged=converged,
        total_samples=n_samples,
        feature_names=feature_names,
        inertia=inertia,
    )


def _generate_subgenre_description(
    cluster_id: int,
    center: List[float],
    feature_names: List[str],
    feature_importance: Dict[str, float],
    sample_count: int,
) -> Tuple[str, str]:
    """
    生成子品类名称和描述。

    基于特征差异自动生成描述性名称。
    """
    # 找出差异最大的前3个特征
    sorted_features = sorted(
        feature_importance.items(),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:3]

    # 生成名称（简单版：基于最显著的特征）
    if sorted_features:
        top_feature, top_diff = sorted_features[0]
        if top_diff > 20:
            name = f"高{top_feature}型"
        elif top_diff < -20:
            name = f"低{top_feature}型"
        else:
            name = f"子品类{cluster_id + 1}"
    else:
        name = f"子品类{cluster_id + 1}"

    # 生成描述
    desc_parts = [f"共 {sample_count} 部作品"]

    for feat_name, diff in sorted_features:
        if diff > 10:
            desc_parts.append(f"{feat_name}显著偏高（+{diff:.0f}%）")
        elif diff < -10:
            desc_parts.append(f"{feat_name}显著偏低（{diff:.0f}%）")

    description = "，".join(desc_parts)

    return name, description


# ============================================================
# 轮廓系数（可选，用于评估聚类质量）
# ============================================================

def calculate_silhouette_score(
    features: List[List[float]],
    labels: List[int],
    distance_metric: str = "euclidean",
) -> float:
    """
    计算轮廓系数（Silhouette Score）。

    用于评估聚类质量，范围 [-1, 1]，越接近 1 越好。
    """
    if not features or len(set(labels)) < 2:
        return 0.0

    n_samples = len(features)

    if distance_metric == "euclidean":
        dist_func = euclidean_distance
    elif distance_metric == "cosine":
        dist_func = lambda a, b: 1 - cosine_similarity(a, b)
    elif distance_metric == "manhattan":
        dist_func = manhattan_distance
    else:
        raise ValueError(f"未知的距离度量：{distance_metric}")

    silhouette_scores = []

    for i in range(n_samples):
        # a(i): 同簇内的平均距离
        same_cluster = [j for j in range(n_samples) if labels[j] == labels[i] and j != i]
        if not same_cluster:
            a_i = 0
        else:
            a_i = sum(dist_func(features[i], features[j]) for j in same_cluster) / len(same_cluster)

        # b(i): 最近其他簇的平均距离
        other_clusters = set(labels) - {labels[i]}
        b_i = float("inf")
        for other_label in other_clusters:
            other_samples = [j for j in range(n_samples) if labels[j] == other_label]
            if other_samples:
                avg_dist = sum(dist_func(features[i], features[j]) for j in other_samples) / len(other_samples)
                b_i = min(b_i, avg_dist)

        # s(i) = (b - a) / max(a, b)
        if max(a_i, b_i) == 0:
            s_i = 0
        else:
            s_i = (b_i - a_i) / max(a_i, b_i)

        silhouette_scores.append(s_i)

    return sum(silhouette_scores) / len(silhouette_scores)


# ============================================================
# 便捷函数
# ============================================================

def get_cluster_summary(result: SubgenreDiscoveryResult) -> List[Dict]:
    """获取聚类摘要列表。"""
    summary = []
    for cluster in result.clusters:
        # 前3个最重要特征
        top_features = sorted(
            cluster.feature_importance.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:3]

        summary.append({
            "cluster_id": cluster.cluster_id,
            "name": cluster.name,
            "description": cluster.description,
            "sample_count": cluster.sample_count,
            "representative_count": len(cluster.representative_samples),
            "top_features": top_features,
        })
    return summary


def assign_to_cluster(
    sample: List[float],
    result: SubgenreDiscoveryResult,
) -> Tuple[int, float]:
    """
    将新样本分配到最近的聚类。

    Returns:
        (cluster_id, distance)
    """
    if not result.clusters:
        return -1, float("inf")

    distances = []
    for cluster in result.clusters:
        dist = euclidean_distance(sample, cluster.center)
        distances.append((cluster.cluster_id, dist))

    distances.sort(key=lambda x: x[1])
    return distances[0]
