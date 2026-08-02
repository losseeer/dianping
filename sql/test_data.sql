-- =====================================================================
-- 测试数据生成脚本 - 后端 11 张表
-- 生成时间: 2026-07-31 18:24:17
-- 美食30家，其余各类型10家，其余表适量数据
-- =====================================================================

SET NAMES utf8mb4;
USE dingping;
SET FOREIGN_KEY_CHECKS = 0;

-- ===========================================================
-- 1. tb_shop 商铺数据（新增106条，共计120条）
-- ===========================================================

INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (15, '老杭帮菜馆', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '上城区', '湖滨银泰303号', 120.154453, 30.259662, 112, 0000014728, 0000001193, 38, '10:00-22:00', '2026-06-16 18:24:17', '2026-06-16 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (16, '川味观火锅', 1, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '教工路302号', 120.108746, 30.280214, 56, 0000036881, 0000003307, 48, '10:00-22:00', '2026-04-11 18:24:17', '2026-04-11 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (17, '日式拉面小馆', 1, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '萧山区', '萧山万象汇184号', 120.266905, 30.161115, 105, 0000022159, 0000000887, 37, '10:00-22:00', '2026-02-16 18:24:17', '2026-02-16 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (18, '韩式烤肉乐园', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '文三路296号', 120.109189, 30.271449, 299, 0000024907, 0000001341, 44, '10:00-22:00', '2026-06-08 18:24:17', '2026-06-08 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (19, '粤式茶楼', 1, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰326号', 120.159116, 30.241576, 70, 0000015356, 0000000877, 47, '10:00-22:00', '2025-12-24 18:24:17', '2025-12-24 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (20, '西北面庄', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '江干区', '万象城274号', 120.18838, 30.250679, 289, 0000044896, 0000010667, 37, '10:00-22:00', '2026-04-09 18:24:17', '2026-04-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (21, '云南过桥米线', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '滨江区', '滨江天街432号', 120.195178, 30.229581, 213, 0000045199, 0000009175, 42, '10:00-22:00', '2026-06-15 18:24:17', '2026-06-15 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (22, '泰式料理店', 1, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '万象城203号', 120.196047, 30.242648, 283, 0000037270, 0000011812, 45, '10:00-22:00', '2026-04-19 18:24:17', '2026-04-19 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (23, '意大利披萨屋', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '拱墅区', '远洋乐堤港186号', 120.135585, 30.3198, 187, 0000017319, 0000004838, 48, '10:00-22:00', '2025-10-14 18:24:17', '2025-10-14 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (24, '墨西哥塔可店', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '滨江区', '滨江天街306号', 120.183636, 30.191885, 78, 0000010116, 0000002620, 40, '10:00-22:00', '2025-12-18 18:24:17', '2025-12-18 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (25, '潮汕牛肉火锅', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '下城区', '嘉里中心394号', 120.189845, 30.271165, 298, 0000036356, 0000000238, 38, '10:00-22:00', '2026-05-05 18:24:17', '2026-05-05 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (26, '重庆小面馆', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '远洋乐堤港260号', 120.147391, 30.308149, 294, 0000047423, 0000014399, 43, '10:00-22:00', '2025-08-08 18:24:17', '2025-08-08 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (27, '新疆大盘鸡', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '余杭区', '西溪印象城251号', 120.074359, 30.266114, 245, 0000010687, 0000002259, 35, '10:00-22:00', '2025-12-28 18:24:17', '2025-12-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (28, '东北饺子馆', 1, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港66号', 120.139578, 30.299635, 195, 0000005261, 0000000225, 50, '10:00-22:00', '2025-09-23 18:24:17', '2025-09-23 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (29, '海南椰子鸡', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '拱墅区', '大关205号', 120.140602, 30.324897, 158, 0000013980, 0000004467, 41, '10:00-22:00', '2025-11-19 18:24:17', '2025-11-19 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (30, '日式居酒屋', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '余杭区', '西溪印象城4号', 120.068059, 30.269916, 66, 0000022256, 0000000222, 42, '10:00-22:00', '2026-03-06 18:24:17', '2026-03-06 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (31, '法式西餐厅', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '教工路110号', 120.136217, 30.294385, 68, 0000033795, 0000003949, 43, '10:00-22:00', '2025-09-12 18:24:17', '2025-09-12 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (32, '越南河粉店', 1, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '下城区', '嘉里中心182号', 120.168907, 30.281385, 256, 0000026777, 0000003169, 38, '10:00-22:00', '2025-11-04 18:24:17', '2025-11-04 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (33, '印度咖喱屋', 1, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '萧山区', '萧山万象汇410号', 120.252167, 30.176138, 215, 0000006549, 0000000298, 47, '10:00-22:00', '2026-03-25 18:24:17', '2026-03-25 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (34, '土耳其烤肉店', 1, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '拱墅区', '运河上街414号', 120.151451, 30.305607, 96, 0000018354, 0000003839, 42, '10:00-22:00', '2026-06-06 18:24:17', '2026-06-06 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (35, '台式卤肉饭', 1, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '上城区', '湖滨银泰249号', 120.189971, 30.263441, 298, 0000006212, 0000001947, 42, '10:00-22:00', '2025-12-08 18:24:17', '2025-12-08 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (36, '好乐迪KTV', 2, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '西湖区', '文三路80号', 120.086585, 30.250086, 149, 0000017480, 0000003777, 44, '12:00-06:00', '2026-03-12 18:24:17', '2026-03-12 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (37, '钱柜KTV', 2, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '文三路30号', 120.103167, 30.271688, 130, 0000003846, 0000000152, 50, '12:00-06:00', '2026-03-28 18:24:17', '2026-03-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (38, '麦乐迪KTV', 2, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '教工路318号', 120.123801, 30.287009, 110, 0000026561, 0000002014, 42, '12:00-06:00', '2025-09-06 18:24:17', '2025-09-06 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (39, '欢乐迪KTV', 2, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '下城区', '嘉里中心203号', 120.170911, 30.287388, 102, 0000043991, 0000011784, 45, '12:00-06:00', '2025-11-09 18:24:17', '2025-11-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (40, '新歌量贩KTV', 2, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '江干区', '万象城260号', 120.217161, 30.277429, 52, 0000030134, 0000009274, 38, '12:00-06:00', '2026-01-04 18:24:17', '2026-01-04 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (41, '时尚造型沙龙', 3, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '教工路342号', 120.135171, 30.274781, 130, 0000028816, 0000008950, 44, '09:00-21:00', '2026-05-09 18:24:17', '2026-05-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (42, '丝语美发工作室', 3, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '大关368号', 120.140579, 30.325589, 430, 0000036356, 0000002596, 43, '09:00-21:00', '2025-08-11 18:24:17', '2025-08-11 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (43, '尖端烫染中心', 3, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '远洋乐堤港2号', 120.150216, 30.300045, 483, 0000003429, 0000000239, 48, '09:00-21:00', '2025-08-09 18:24:17', '2025-08-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (44, '剪爱造型', 3, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港484号', 120.136463, 30.307673, 411, 0000028128, 0000009239, 35, '09:00-21:00', '2025-09-25 18:24:17', '2025-09-25 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (45, '韩式剪烫', 3, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '西湖区', '文三路461号', 120.113384, 30.2733, 125, 0000028266, 0000002138, 36, '09:00-21:00', '2026-03-16 18:24:17', '2026-03-16 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (46, '雅琪美容美发', 3, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰500号', 120.159981, 30.234112, 449, 0000036792, 0000006708, 39, '09:00-21:00', '2026-06-19 18:24:17', '2026-06-19 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (47, '名流造型工作室', 3, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '大关404号', 120.159463, 30.303287, 260, 0000044003, 0000014206, 42, '09:00-21:00', '2025-12-18 18:24:17', '2025-12-18 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (48, '都市快剪', 3, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '西湖区', '文三路13号', 120.114344, 30.258897, 468, 0000030266, 0000005778, 44, '09:00-21:00', '2025-12-09 18:24:17', '2025-12-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (49, '飘逸美发', 3, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '万象城481号', 120.191144, 30.242777, 445, 0000018392, 0000002926, 47, '09:00-21:00', '2026-02-18 18:24:17', '2026-02-18 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (50, '炫彩造型', 3, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '拱墅区', '大关224号', 120.153224, 30.329342, 69, 0000007204, 0000001829, 46, '09:00-21:00', '2026-05-03 18:24:17', '2026-05-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (51, '力美健健身房', 4, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '江干区', '来福士187号', 120.22598, 30.247603, 52, 0000046550, 0000007194, 35, '06:00-23:00', '2026-01-13 18:24:17', '2026-01-13 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (52, '超级猩猩健身', 4, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '下城区', '嘉里中心357号', 120.162557, 30.283921, 183, 0000033334, 0000005117, 48, '06:00-23:00', '2026-04-27 18:24:17', '2026-04-27 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (53, '一兆韦德健身', 4, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '运河上街156号', 120.146818, 30.337615, 119, 0000040438, 0000009374, 44, '06:00-23:00', '2025-11-23 18:24:17', '2025-11-23 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (54, '乐刻运动馆', 4, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '下城区', '嘉里中心338号', 120.174266, 30.26289, 256, 0000029077, 0000003551, 50, '06:00-23:00', '2025-10-11 18:24:17', '2025-10-11 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (55, 'keep健身工作室', 4, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰13号', 120.175318, 30.243408, 150, 0000044192, 0000005135, 42, '06:00-23:00', '2025-10-31 18:24:17', '2025-10-31 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (56, '瑜伽生活馆', 4, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '下城区', '嘉里中心254号', 120.18399, 30.252913, 242, 0000041372, 0000009481, 41, '06:00-23:00', '2026-04-17 18:24:17', '2026-04-17 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (57, '动感单车俱乐部', 4, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '上城区', '湖滨银泰26号', 120.177505, 30.265706, 84, 0000027962, 0000003635, 40, '06:00-23:00', '2026-04-30 18:24:17', '2026-04-30 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (58, '游泳健身中心', 4, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '滨江区', '滨江天街460号', 120.185334, 30.208586, 192, 0000049596, 0000014552, 48, '06:00-23:00', '2025-11-13 18:24:17', '2025-11-13 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (59, '搏击格斗馆', 4, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港40号', 120.160071, 30.323595, 171, 0000034263, 0000007989, 42, '06:00-23:00', '2026-03-03 18:24:17', '2026-03-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (60, '普拉提工作室', 4, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '远洋乐堤港362号', 120.143434, 30.325721, 71, 0000009168, 0000000667, 42, '06:00-23:00', '2025-12-01 18:24:17', '2025-12-01 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (61, '颐和足道馆', 5, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '江干区', '来福士439号', 120.203235, 30.258637, 95, 0000013655, 0000003491, 47, '10:00-23:00', '2025-10-30 18:24:17', '2025-10-30 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (62, '康乐按摩中心', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '文三路140号', 120.11771, 30.261945, 179, 0000027560, 0000008868, 42, '10:00-23:00', '2026-06-17 18:24:17', '2026-06-17 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (63, '御足轩足疗', 5, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '江干区', '来福士465号', 120.203445, 30.267166, 183, 0000047559, 0000002754, 49, '10:00-23:00', '2025-09-16 18:24:17', '2025-09-16 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (64, '富侨保健按摩', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰168号', 120.151084, 30.25571, 114, 0000030357, 0000003027, 36, '10:00-23:00', '2026-01-15 18:24:17', '2026-01-15 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (65, '华夏良子', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '江干区', '万象城384号', 120.210449, 30.255165, 272, 0000027727, 0000004183, 37, '10:00-23:00', '2026-01-03 18:24:17', '2026-01-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (66, '泰式SPA按摩', 5, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '运河上街430号', 120.156006, 30.331249, 246, 0000002738, 0000000822, 35, '10:00-23:00', '2026-04-14 18:24:17', '2026-04-14 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (67, '中医推拿馆', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '运河上街311号', 120.135049, 30.326778, 224, 0000014384, 0000003859, 43, '10:00-23:00', '2026-04-09 18:24:17', '2026-04-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (68, '养生堂足浴', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '远洋乐堤港39号', 120.134324, 30.291027, 159, 0000037835, 0000011147, 47, '10:00-23:00', '2026-05-10 18:24:17', '2026-05-10 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (69, '轻松驿站足疗', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '萧山区', '萧山万象汇339号', 120.280899, 30.184012, 233, 0000008033, 0000002368, 36, '10:00-23:00', '2025-10-15 18:24:17', '2025-10-15 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (70, '金手指按摩', 5, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰363号', 120.163649, 30.263983, 290, 0000032225, 0000001779, 48, '10:00-23:00', '2026-04-02 18:24:17', '2026-04-02 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (71, '美丽田园SPA', 6, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '萧山区', '萧山万象汇166号', 120.27087, 30.176018, 730, 0000035369, 0000007971, 49, '10:00-22:00', '2026-02-09 18:24:17', '2026-02-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (72, '克丽缇娜美容', 6, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '滨江区', '滨江天街436号', 120.189755, 30.208588, 724, 0000043890, 0000006259, 45, '10:00-22:00', '2025-10-25 18:24:17', '2025-10-25 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (73, '思妍丽美容SPA', 6, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '运河上街265号', 120.144193, 30.310334, 386, 0000039169, 0000011538, 43, '10:00-22:00', '2026-02-28 18:24:17', '2026-02-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (74, '奈瑞儿SPA', 6, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '萧山区', '萧山万象汇48号', 120.266257, 30.172207, 346, 0000045359, 0000007850, 50, '10:00-22:00', '2025-12-06 18:24:17', '2025-12-06 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (75, '自然美美容', 6, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '萧山区', '萧山万象汇181号', 120.259732, 30.176558, 477, 0000031115, 0000009118, 46, '10:00-22:00', '2026-02-13 18:24:17', '2026-02-13 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (76, '法兰琳卡美容SPA', 6, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港379号', 120.140056, 30.294826, 297, 0000020779, 0000001029, 40, '10:00-22:00', '2025-09-03 18:24:17', '2025-09-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (77, '伊美尔SPA馆', 6, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '余杭区', '西溪印象城8号', 120.073872, 30.29922, 298, 0000019514, 0000001913, 46, '10:00-22:00', '2026-04-28 18:24:17', '2026-04-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (78, '花瓣雨美容', 6, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港294号', 120.131821, 30.292181, 399, 0000045805, 0000002118, 50, '10:00-22:00', '2025-10-29 18:24:17', '2025-10-29 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (79, '悦颜SPA', 6, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '滨江区', '滨江天街38号', 120.193628, 30.22862, 358, 0000031408, 0000001919, 37, '10:00-22:00', '2026-04-15 18:24:17', '2026-04-15 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (80, '凝脂美容SPA', 6, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '大关398号', 120.162446, 30.327965, 187, 0000016365, 0000001020, 48, '10:00-22:00', '2025-11-13 18:24:17', '2025-11-13 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (81, '欢乐城堡儿童乐园', 7, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '滨江区', '滨江天街486号', 120.191894, 30.213541, 159, 0000020113, 0000004708, 36, '10:00-21:00', '2026-02-16 18:24:17', '2026-02-16 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (82, '宝贝当家亲子园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰353号', 120.153247, 30.239595, 191, 0000005019, 0000000370, 35, '10:00-21:00', '2026-02-02 18:24:17', '2026-02-02 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (83, '奇乐儿儿童乐园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '文三路218号', 120.089259, 30.278278, 166, 0000004764, 0000001457, 42, '10:00-21:00', '2026-03-08 18:24:17', '2026-03-08 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (84, '悠游堂亲子乐园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰225号', 120.15596, 30.240625, 86, 0000004779, 0000000172, 40, '10:00-21:00', '2026-01-27 18:24:17', '2026-01-27 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (85, '卡通尼乐园', 7, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '萧山区', '萧山万象汇456号', 120.2661, 30.16089, 188, 0000032461, 0000007222, 37, '10:00-21:00', '2025-08-26 18:24:17', '2025-08-26 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (86, '奥飞欢乐世界', 7, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '远洋乐堤港391号', 120.131035, 30.299157, 197, 0000038577, 0000000389, 43, '10:00-21:00', '2025-10-09 18:24:17', '2025-10-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (87, '大白鲸乐园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰210号', 120.167689, 30.241126, 199, 0000028666, 0000008106, 37, '10:00-21:00', '2026-05-09 18:24:17', '2026-05-09 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (88, '木马王国儿童乐园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '大关162号', 120.143192, 30.317747, 123, 0000043523, 0000006611, 36, '10:00-21:00', '2026-05-03 18:24:17', '2026-05-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (89, '开心娃娃亲子乐园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '江干区', '来福士97号', 120.224596, 30.272997, 50, 0000043200, 0000014293, 49, '10:00-21:00', '2025-08-17 18:24:17', '2025-08-17 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (90, '童趣探索乐园', 7, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '滨江区', '滨江天街451号', 120.205016, 30.2204, 102, 0000017601, 0000004549, 39, '10:00-21:00', '2026-04-30 18:24:17', '2026-04-30 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (91, 'MUSE酒吧', 8, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '文三路283号', 120.118926, 30.274355, 141, 0000046616, 0000002644, 44, '18:00-04:00', '2026-03-08 18:24:17', '2026-03-08 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (92, 'MIX俱乐部', 8, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '教工路213号', 120.118458, 30.264699, 293, 0000010190, 0000002091, 44, '18:00-04:00', '2026-02-27 18:24:17', '2026-02-27 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (93, '苏荷酒吧', 8, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '滨江区', '滨江天街175号', 120.202051, 30.205343, 233, 0000033408, 0000002286, 37, '18:00-04:00', '2026-06-30 18:24:17', '2026-06-30 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (94, '菲芘酒吧', 8, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港177号', 120.159042, 30.323499, 228, 0000043349, 0000008072, 39, '18:00-04:00', '2025-09-26 18:24:17', '2025-09-26 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (95, '外滩18号酒吧', 8, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '来福士23号', 120.208214, 30.252871, 128, 0000045811, 0000003962, 47, '18:00-04:00', '2025-12-18 18:24:17', '2025-12-18 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (96, '海伦司小酒馆', 8, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '来福士446号', 120.229537, 30.271696, 246, 0000010068, 0000002078, 36, '18:00-04:00', '2026-05-11 18:24:17', '2026-05-11 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (97, '胡桃里音乐酒馆', 8, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '余杭区', '西溪印象城174号', 120.086418, 30.260614, 116, 0000026968, 0000002579, 37, '18:00-04:00', '2025-08-03 18:24:17', '2025-08-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (98, 'Mao Livehouse', 8, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '教工路447号', 120.134071, 30.294094, 299, 0000035071, 0000006276, 45, '18:00-04:00', '2025-08-19 18:24:17', '2025-08-19 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (99, '隐泉日式酒吧', 8, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '西湖区', '教工路228号', 120.109391, 30.287376, 153, 0000015008, 0000000790, 48, '18:00-04:00', '2026-06-17 18:24:17', '2026-06-17 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (100, '精酿啤酒工坊', 8, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '文三路290号', 120.092975, 30.252245, 171, 0000024665, 0000003578, 39, '18:00-04:00', '2026-04-05 18:24:17', '2026-04-05 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (101, '轰趴时光别墅', 9, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '拱墅区', '大关327号', 120.133159, 30.324834, 446, 0000032715, 0000009604, 39, '10:00-23:00', '2026-02-21 18:24:17', '2026-02-21 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (102, '同学聚会馆', 9, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '上城区', '湖滨银泰484号', 120.150376, 30.262185, 494, 0000044507, 0000009005, 40, '10:00-23:00', '2026-01-29 18:24:17', '2026-01-29 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (103, '派对空间轰趴馆', 9, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '上城区', '湖滨银泰122号', 120.188481, 30.257613, 667, 0000019899, 0000001681, 47, '10:00-23:00', '2025-12-30 18:24:17', '2025-12-30 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (104, '欢乐轰趴馆', 9, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '下城区', '嘉里中心467号', 120.161835, 30.277971, 222, 0000043237, 0000006534, 43, '10:00-23:00', '2026-02-05 18:24:17', '2026-02-05 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (105, '好友聚会别墅', 9, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '运河上街463号', 120.154283, 30.314093, 394, 0000040790, 0000004156, 39, '10:00-23:00', '2026-01-24 18:24:17', '2026-01-24 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (106, '周末派对轰趴', 9, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '滨江区', '滨江天街90号', 120.181335, 30.204594, 334, 0000006006, 0000001912, 44, '10:00-23:00', '2025-09-28 18:24:17', '2025-09-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (107, '主题轰趴馆', 9, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '万象城412号', 120.201234, 30.276539, 368, 0000016940, 0000003997, 44, '10:00-23:00', '2026-05-24 18:24:17', '2026-05-24 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (108, '轰趴大本营', 9, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '大关136号', 120.160166, 30.299025, 606, 0000036624, 0000006042, 37, '10:00-23:00', '2025-11-11 18:24:17', '2025-11-11 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (109, '青春轰趴馆', 9, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '江干区', '万象城242号', 120.206913, 30.266894, 798, 0000025070, 0000006136, 38, '10:00-23:00', '2025-09-17 18:24:17', '2025-09-17 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (110, '快乐时光轰趴', 9, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '万象城333号', 120.21661, 30.248855, 264, 0000041741, 0000013548, 49, '10:00-23:00', '2026-04-21 18:24:17', '2026-04-21 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (111, '美甲工作室', 10, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '西湖区', '文三路199号', 120.11785, 30.262175, 176, 0000007710, 0000000448, 42, '10:00-21:00', '2025-09-28 18:24:17', '2025-09-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (112, '纤指百媚美甲', 10, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '江干区', '来福士481号', 120.213494, 30.269064, 276, 0000027289, 0000001672, 50, '10:00-21:00', '2025-12-24 18:24:17', '2025-12-24 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (113, '甲如是你美甲', 10, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '拱墅区', '运河上街32号', 120.147735, 30.338022, 268, 0000023868, 0000000863, 46, '10:00-21:00', '2026-03-26 18:24:17', '2026-03-26 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (114, '指间艺术美甲', 10, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png', '西湖区', '教工路125号', 120.13796, 30.292968, 73, 0000043535, 0000003525, 35, '10:00-21:00', '2026-03-18 18:24:17', '2026-03-18 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (115, '樱花美甲美睫', 10, 'https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '西湖区', '教工路142号', 120.133193, 30.282168, 200, 0000014252, 0000001958, 45, '10:00-21:00', '2025-09-28 18:24:17', '2025-09-28 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (116, '爱美美甲美睫', 10, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '拱墅区', '远洋乐堤港302号', 120.161941, 30.294397, 271, 0000001789, 0000000184, 35, '10:00-21:00', '2026-04-03 18:24:17', '2026-04-03 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (117, '美甲美睫工坊', 10, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '拱墅区', '远洋乐堤港263号', 120.132096, 30.319669, 184, 0000007548, 0000000310, 50, '10:00-21:00', '2025-11-12 18:24:17', '2025-11-12 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (118, '精致美甲沙龙', 10, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '余杭区', '西溪印象城32号', 120.058862, 30.284604, 236, 0000043281, 0000008593, 44, '10:00-21:00', '2025-11-25 18:24:17', '2025-11-25 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (119, '指尖蜜语美甲', 10, 'https://p0.meituan.net/biztone/694233_1619500156517.jpeg,https://p0.meituan.net/bbia/c1870d570e73accbc9fee90b48faca41195272.jpg', '上城区', '湖滨银泰34号', 120.154318, 30.258496, 163, 0000004916, 0000000215, 45, '10:00-21:00', '2025-08-16 18:24:17', '2025-08-16 18:24:17');
INSERT INTO `tb_shop` (`id`, `name`, `type_id`, `images`, `area`, `address`, `x`, `y`, `avg_price`, `sold`, `comments`, `score`, `open_hours`, `create_time`, `update_time`) VALUES (120, '美睫美甲studio', 10, 'https://img.meituan.net/msmerchant/876ca8983f7395556eda9ceb064e6bc51840883.png,https://p0.meituan.net/biztone/694233_1619500156517.jpeg', '上城区', '湖滨银泰51号', 120.173415, 30.258486, 147, 0000039250, 0000008742, 44, '10:00-21:00', '2025-07-31 18:24:17', '2025-07-31 18:24:17');

-- 共新增 106 家商铺，ID: 15 ~ 120

-- ===========================================================
-- 2. tb_voucher 优惠券数据
-- ===========================================================

INSERT INTO `tb_voucher` VALUES (2, 15, '老杭帮菜馆代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 47500, 48000, 0, 1, '2026-05-27 18:24:17', '2026-05-27 18:24:17');
INSERT INTO `tb_voucher` VALUES (3, 16, '川味观火锅代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 28500, 29000, 0, 1, '2026-05-30 18:24:17', '2026-05-30 18:24:17');
INSERT INTO `tb_voucher` VALUES (4, 17, '日式拉面小馆代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 21000, 0, 1, '2026-05-31 18:24:17', '2026-05-31 18:24:17');
INSERT INTO `tb_voucher` VALUES (5, 18, '韩式烤肉乐园代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 28500, 28750, 0, 1, '2026-06-11 18:24:17', '2026-06-11 18:24:17');
INSERT INTO `tb_voucher` VALUES (6, 19, '粤式茶楼代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 28500, 29500, 0, 1, '2026-06-19 18:24:17', '2026-06-19 18:24:17');
INSERT INTO `tb_voucher` VALUES (7, 20, '西北面庄代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 19500, 0, 1, '2026-05-22 18:24:17', '2026-05-22 18:24:17');
INSERT INTO `tb_voucher` VALUES (8, 21, '云南过桥米线代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 5000, 0, 1, '2026-07-11 18:24:17', '2026-07-11 18:24:17');
INSERT INTO `tb_voucher` VALUES (9, 22, '泰式料理店代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 6750, 0, 1, '2026-07-09 18:24:17', '2026-07-09 18:24:17');
INSERT INTO `tb_voucher` VALUES (10, 23, '意大利披萨屋代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 19500, 0, 1, '2026-05-11 18:24:17', '2026-05-11 18:24:17');
INSERT INTO `tb_voucher` VALUES (11, 24, '墨西哥塔可店代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 9750, 0, 1, '2026-05-11 18:24:17', '2026-05-11 18:24:17');
INSERT INTO `tb_voucher` VALUES (12, 25, '潮汕牛肉火锅代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 47500, 48500, 0, 1, '2026-07-06 18:24:17', '2026-07-06 18:24:17');
INSERT INTO `tb_voucher` VALUES (13, 26, '重庆小面馆代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 28500, 29500, 0, 1, '2026-05-28 18:24:17', '2026-05-28 18:24:17');
INSERT INTO `tb_voucher` VALUES (14, 27, '新疆大盘鸡代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 5750, 0, 1, '2026-05-06 18:24:17', '2026-05-06 18:24:17');
INSERT INTO `tb_voucher` VALUES (15, 28, '东北饺子馆代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 20000, 0, 1, '2026-07-08 18:24:17', '2026-07-08 18:24:17');
INSERT INTO `tb_voucher` VALUES (16, 29, '海南椰子鸡代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 47500, 52500, 0, 1, '2026-06-24 18:24:17', '2026-06-24 18:24:17');
INSERT INTO `tb_voucher` VALUES (17, 30, '日式居酒屋代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 9500, 11500, 0, 1, '2026-06-23 18:24:17', '2026-06-23 18:24:17');
INSERT INTO `tb_voucher` VALUES (18, 31, '法式西餐厅代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 5750, 0, 1, '2026-05-11 18:24:17', '2026-05-11 18:24:17');
INSERT INTO `tb_voucher` VALUES (19, 32, '越南河粉店代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 19250, 0, 1, '2026-06-16 18:24:17', '2026-06-16 18:24:17');
INSERT INTO `tb_voucher` VALUES (20, 33, '印度咖喱屋代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 47500, 48000, 0, 1, '2026-05-28 18:24:17', '2026-05-28 18:24:17');
INSERT INTO `tb_voucher` VALUES (21, 34, '土耳其烤肉店代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 47500, 52500, 0, 1, '2026-05-04 18:24:17', '2026-05-04 18:24:17');
INSERT INTO `tb_voucher` VALUES (22, 35, '台式卤肉饭代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 47500, 47750, 0, 1, '2026-05-05 18:24:17', '2026-05-05 18:24:17');
INSERT INTO `tb_voucher` VALUES (23, 36, '好乐迪KTV代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 19250, 0, 1, '2026-06-28 18:24:17', '2026-06-28 18:24:17');
INSERT INTO `tb_voucher` VALUES (24, 37, '钱柜KTV代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 20000, 0, 1, '2026-06-08 18:24:17', '2026-06-08 18:24:17');
INSERT INTO `tb_voucher` VALUES (25, 38, '麦乐迪KTV代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 19250, 0, 1, '2026-06-28 18:24:17', '2026-06-28 18:24:17');
INSERT INTO `tb_voucher` VALUES (26, 39, '欢乐迪KTV代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 9500, 14500, 0, 1, '2026-05-31 18:24:17', '2026-05-31 18:24:17');
INSERT INTO `tb_voucher` VALUES (27, 40, '新歌量贩KT代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 5250, 0, 1, '2026-07-18 18:24:17', '2026-07-18 18:24:17');
INSERT INTO `tb_voucher` VALUES (28, 41, '时尚造型沙龙代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 4750, 9750, 0, 1, '2026-06-24 18:24:17', '2026-06-24 18:24:17');
INSERT INTO `tb_voucher` VALUES (29, 42, '丝语美发工作代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 28500, 30500, 0, 1, '2026-05-24 18:24:17', '2026-05-24 18:24:17');
INSERT INTO `tb_voucher` VALUES (30, 43, '尖端烫染中心代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 19500, 0, 1, '2026-06-04 18:24:17', '2026-06-04 18:24:17');
INSERT INTO `tb_voucher` VALUES (31, 44, '剪爱造型代金券', '周一至周日均可使用', '全场通用\n无需预约\n可无限叠加\不兑现、不找零', 19000, 20000, 0, 1, '2026-05-10 18:24:17', '2026-05-10 18:24:17');
INSERT INTO `tb_voucher` VALUES (32, 15, '100元代金券限时秒杀', '仅限工作日使用', '限购1张\n不可叠加\n过期自动失效', 5000, 10000, 1, 1, '2026-07-31 18:24:17', '2026-07-31 18:24:17');
INSERT INTO `tb_voucher` VALUES (33, 16, '200元代金券限时秒杀', '仅限堂食使用', '限购1张\n不可叠加\n过期自动失效', 10000, 20000, 1, 1, '2026-07-31 18:24:17', '2026-07-31 18:24:17');
INSERT INTO `tb_voucher` VALUES (34, 17, '50元代金券新人秒杀', '新用户专享', '限购1张\n不可叠加\n过期自动失效', 2500, 5000, 1, 1, '2026-07-31 18:24:17', '2026-07-31 18:24:17');

-- 共新增 33 张优惠券（含3张秒杀券）

-- ===========================================================
-- 3. tb_seckill_voucher 秒杀券信息
-- ===========================================================

INSERT INTO `tb_seckill_voucher` VALUES (32, 100, '2026-07-31 17:24:17', '2026-07-31 17:24:17', '2026-08-07 18:24:17', '2026-08-07 18:24:17');
INSERT INTO `tb_seckill_voucher` VALUES (33, 50, '2026-07-31 17:24:17', '2026-07-31 17:24:17', '2026-08-07 18:24:17', '2026-08-07 18:24:17');
INSERT INTO `tb_seckill_voucher` VALUES (34, 200, '2026-07-31 17:24:17', '2026-07-31 17:24:17', '2026-08-07 18:24:17', '2026-08-07 18:24:17');

-- 共3条秒杀券记录

-- ===========================================================
-- 4. tb_blog 探店笔记
-- ===========================================================

INSERT INTO `tb_blog` VALUES (8, 91, 114, '探店MUSE酒吧', '/imgs/blogs/blog6.jpg', '第一次来MUSE酒吧，超出预期！环境优雅，服务热情，下次还会再来。', 347, 37, '2026-06-29 18:24:17', '2026-06-29 18:24:17');
INSERT INTO `tb_blog` VALUES (9, 25, 540, '探店潮汕牛肉火锅', '/imgs/blogs/blog1.jpg', '第一次来潮汕牛肉火锅，超出预期！环境优雅，服务热情，下次还会再来。', 112, 25, '2026-06-22 18:24:17', '2026-06-22 18:24:17');
INSERT INTO `tb_blog` VALUES (10, 21, 57, '探店云南过桥米线', '/imgs/blogs/blog2.jpg', '环境真的很不错，云南过桥米线的装修很有格调，服务也很周到。推荐推荐！', 154, 13, '2026-06-11 18:24:17', '2026-06-11 18:24:17');
INSERT INTO `tb_blog` VALUES (11, 34, 141, '探店土耳其烤肉店', '/imgs/blogs/blog3.jpg', '第一次来土耳其烤肉店，超出预期！环境优雅，服务热情，下次还会再来。', 167, 7, '2026-07-30 18:24:17', '2026-07-30 18:24:17');
INSERT INTO `tb_blog` VALUES (12, 35, 510, '探店台式卤肉饭', '/imgs/blogs/blog2.jpg', '周末和朋友约了台式卤肉饭，整体体验打满分，值得二刷。', 66, 24, '2026-06-26 18:24:17', '2026-06-26 18:24:17');
INSERT INTO `tb_blog` VALUES (13, 111, 721, '探店美甲工作室', '/imgs/blogs/blog5.jpg', '美甲工作室的性价比真的很高，人均不贵就能吃到很好的品质。', 286, 42, '2026-06-09 18:24:17', '2026-06-09 18:24:17');
INSERT INTO `tb_blog` VALUES (14, 94, 363, '探店菲芘酒吧', '/imgs/blogs/blog4.jpg', '今天和朋友一起来菲芘酒吧，体验非常好！菜品新鲜，味道也很正宗。', 441, 47, '2026-07-28 18:24:17', '2026-07-28 18:24:17');
INSERT INTO `tb_blog` VALUES (15, 101, 447, '探店轰趴时光别墅', '/imgs/blogs/blog4.jpg', '环境真的很不错，轰趴时光别墅的装修很有格调，服务也很周到。推荐推荐！', 471, 4, '2026-06-05 18:24:17', '2026-06-05 18:24:17');
INSERT INTO `tb_blog` VALUES (16, 49, 321, '探店飘逸美发', '/imgs/blogs/blog5.jpg', '周末和朋友约了飘逸美发，整体体验打满分，值得二刷。', 207, 45, '2026-06-20 18:24:17', '2026-06-20 18:24:17');
INSERT INTO `tb_blog` VALUES (17, 71, 428, '探店美丽田园SPA', '/imgs/blogs/blog1.jpg', '第一次来美丽田园SPA，超出预期！环境优雅，服务热情，下次还会再来。', 207, 1, '2026-07-10 18:24:17', '2026-07-10 18:24:17');
INSERT INTO `tb_blog` VALUES (18, 99, 176, '探店隐泉日式酒吧', '/imgs/blogs/blog7.jpg', '隐泉日式酒吧的服务真的太棒了，细节满满，让人感觉很温暖。', 353, 23, '2026-07-25 18:24:17', '2026-07-25 18:24:17');
INSERT INTO `tb_blog` VALUES (19, 69, 448, '探店轻松驿站足疗', '/imgs/blogs/blog2.jpg', '今天和朋友一起来轻松驿站足疗，体验非常好！菜品新鲜，味道也很正宗。', 223, 37, '2026-07-05 18:24:17', '2026-07-05 18:24:17');
INSERT INTO `tb_blog` VALUES (20, 77, 537, '探店伊美尔SPA馆', '/imgs/blogs/blog4.jpg', '今天和朋友一起来伊美尔SPA馆，体验非常好！菜品新鲜，味道也很正宗。', 445, 19, '2026-06-13 18:24:17', '2026-06-13 18:24:17');
INSERT INTO `tb_blog` VALUES (21, 92, 348, '探店MIX俱乐部', '/imgs/blogs/blog3.jpg', 'MIX俱乐部的性价比真的很高，人均不贵就能吃到很好的品质。', 398, 10, '2026-07-26 18:24:17', '2026-07-26 18:24:17');
INSERT INTO `tb_blog` VALUES (22, 68, 523, '探店养生堂足浴', '/imgs/blogs/blog5.jpg', '今天和朋友一起来养生堂足浴，体验非常好！菜品新鲜，味道也很正宗。', 261, 12, '2026-06-03 18:24:17', '2026-06-03 18:24:17');
INSERT INTO `tb_blog` VALUES (23, 42, 795, '探店丝语美发工作室', '/imgs/blogs/blog3.jpg', '种草很久的丝语美发工作室终于来了！果然名不虚传，强烈推荐！', 372, 41, '2026-06-08 18:24:17', '2026-06-08 18:24:17');
INSERT INTO `tb_blog` VALUES (24, 80, 152, '探店凝脂美容SPA', '/imgs/blogs/blog1.jpg', '凝脂美容SPA的性价比真的很高，人均不贵就能吃到很好的品质。', 74, 16, '2026-07-18 18:24:17', '2026-07-18 18:24:17');
INSERT INTO `tb_blog` VALUES (25, 29, 178, '探店海南椰子鸡', '/imgs/blogs/blog7.jpg', '网红打卡地海南椰子鸡，氛围感满满！拍照超级出片～', 388, 41, '2026-07-26 18:24:17', '2026-07-26 18:24:17');
INSERT INTO `tb_blog` VALUES (26, 59, 182, '探店搏击格斗馆', '/imgs/blogs/blog4.jpg', '搏击格斗馆的服务真的太棒了，细节满满，让人感觉很温暖。', 386, 36, '2026-06-12 18:24:17', '2026-06-12 18:24:17');
INSERT INTO `tb_blog` VALUES (27, 70, 594, '探店金手指按摩', '/imgs/blogs/blog6.jpg', '金手指按摩的服务真的太棒了，细节满满，让人感觉很温暖。', 473, 36, '2026-06-19 18:24:17', '2026-06-19 18:24:17');

-- 共新增 20 条探店笔记

-- ===========================================================
-- 5. tb_blog_comments 评论
-- ===========================================================

INSERT INTO `tb_blog_comments` VALUES (1, 640, 8, 0, 0, '服务态度很好', 27, 0, '2026-07-11 18:24:17', '2026-07-11 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (2, 324, 8, 0, 0, '下次一定要去试试', 14, 0, '2026-07-29 18:24:17', '2026-07-29 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (3, 481, 8, 0, 0, '收藏了！', 20, 0, '2026-07-22 18:24:17', '2026-07-22 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (4, 606, 9, 0, 0, '看起来好好吃啊！', 11, 0, '2026-07-15 18:24:17', '2026-07-15 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (5, 76, 9, 0, 0, '性价比很高推荐', 14, 0, '2026-07-17 18:24:17', '2026-07-17 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (6, 59, 10, 0, 0, '服务态度很好', 26, 0, '2026-07-22 18:24:17', '2026-07-22 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (7, 661, 11, 0, 0, '种草了种草了！', 19, 0, '2026-07-12 18:24:17', '2026-07-12 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (8, 394, 12, 0, 0, '收藏了！', 18, 0, '2026-07-14 18:24:17', '2026-07-14 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (9, 978, 12, 0, 0, '看起来好好吃啊！', 14, 0, '2026-07-02 18:24:17', '2026-07-02 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (10, 830, 12, 0, 0, '人均多少呀', 20, 0, '2026-07-25 18:24:17', '2026-07-25 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (11, 620, 13, 0, 0, '收藏了！', 16, 0, '2026-07-27 18:24:17', '2026-07-27 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (12, 981, 13, 0, 0, '看起来好好吃啊！', 14, 0, '2026-07-28 18:24:17', '2026-07-28 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (13, 1006, 14, 0, 0, '种草了种草了！', 16, 0, '2026-07-11 18:24:17', '2026-07-11 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (14, 177, 14, 0, 0, '看起来好好吃啊！', 7, 0, '2026-07-09 18:24:17', '2026-07-09 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (15, 450, 15, 0, 0, '看起来环境不错', 16, 0, '2026-07-12 18:24:17', '2026-07-12 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (16, 163, 15, 0, 0, '服务态度很好', 11, 0, '2026-07-02 18:24:17', '2026-07-02 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (17, 397, 16, 0, 0, '楼主拍照技术真好', 24, 0, '2026-07-21 18:24:17', '2026-07-21 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (18, 696, 16, 0, 0, '人均多少呀', 1, 0, '2026-07-06 18:24:17', '2026-07-06 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (19, 663, 17, 0, 0, '服务态度很好', 2, 0, '2026-07-21 18:24:17', '2026-07-21 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (20, 97, 17, 0, 0, '看起来环境不错', 21, 0, '2026-07-19 18:24:17', '2026-07-19 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (21, 291, 17, 0, 0, '性价比很高推荐', 23, 0, '2026-07-04 18:24:17', '2026-07-04 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (22, 988, 18, 0, 0, '人均多少呀', 27, 0, '2026-07-27 18:24:17', '2026-07-27 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (23, 342, 18, 0, 0, '种草了种草了！', 18, 0, '2026-07-10 18:24:17', '2026-07-10 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (24, 145, 18, 0, 0, '服务态度很好', 9, 0, '2026-07-01 18:24:17', '2026-07-01 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (25, 716, 19, 0, 0, '楼主拍照技术真好', 4, 0, '2026-07-12 18:24:17', '2026-07-12 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (26, 726, 19, 0, 0, '种草了种草了！', 9, 0, '2026-07-14 18:24:17', '2026-07-14 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (27, 386, 19, 0, 0, '服务态度很好', 26, 0, '2026-07-27 18:24:17', '2026-07-27 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (28, 720, 20, 0, 0, '看起来环境不错', 2, 0, '2026-07-11 18:24:17', '2026-07-11 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (29, 687, 20, 0, 0, '楼主拍照技术真好', 16, 0, '2026-07-20 18:24:17', '2026-07-20 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (30, 19, 20, 0, 0, '服务态度很好', 9, 0, '2026-07-26 18:24:17', '2026-07-26 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (31, 350, 21, 0, 0, '收藏了！', 6, 0, '2026-07-24 18:24:17', '2026-07-24 18:24:17');
INSERT INTO `tb_blog_comments` VALUES (32, 159, 22, 0, 0, '种草了种草了！', 9, 0, '2026-07-04 18:24:17', '2026-07-04 18:24:17');

-- 共新增 32 条评论

-- ===========================================================
-- 6. tb_follow 关注关系
-- ===========================================================

INSERT INTO `tb_follow` VALUES (1, 808, 104, '2026-05-27 18:24:17');
INSERT INTO `tb_follow` VALUES (2, 790, 553, '2026-05-24 18:24:17');
INSERT INTO `tb_follow` VALUES (3, 39, 678, '2026-06-17 18:24:17');
INSERT INTO `tb_follow` VALUES (4, 898, 785, '2026-05-12 18:24:17');
INSERT INTO `tb_follow` VALUES (5, 135, 612, '2026-06-12 18:24:17');
INSERT INTO `tb_follow` VALUES (6, 158, 167, '2026-07-07 18:24:17');
INSERT INTO `tb_follow` VALUES (7, 852, 710, '2026-05-12 18:24:17');
INSERT INTO `tb_follow` VALUES (8, 829, 925, '2026-07-09 18:24:17');
INSERT INTO `tb_follow` VALUES (9, 739, 449, '2026-07-25 18:24:17');
INSERT INTO `tb_follow` VALUES (10, 421, 374, '2026-05-05 18:24:17');
INSERT INTO `tb_follow` VALUES (11, 737, 244, '2026-06-04 18:24:17');
INSERT INTO `tb_follow` VALUES (12, 626, 292, '2026-06-03 18:24:17');
INSERT INTO `tb_follow` VALUES (13, 240, 547, '2026-06-30 18:24:17');
INSERT INTO `tb_follow` VALUES (14, 317, 989, '2026-05-31 18:24:17');
INSERT INTO `tb_follow` VALUES (15, 926, 856, '2026-07-06 18:24:17');
INSERT INTO `tb_follow` VALUES (16, 377, 695, '2026-05-18 18:24:17');
INSERT INTO `tb_follow` VALUES (17, 1009, 452, '2026-06-01 18:24:17');
INSERT INTO `tb_follow` VALUES (18, 788, 289, '2026-06-12 18:24:17');
INSERT INTO `tb_follow` VALUES (19, 515, 541, '2026-06-07 18:24:17');
INSERT INTO `tb_follow` VALUES (20, 990, 166, '2026-07-05 18:24:17');
INSERT INTO `tb_follow` VALUES (21, 821, 620, '2026-07-13 18:24:17');
INSERT INTO `tb_follow` VALUES (22, 894, 257, '2026-07-24 18:24:17');
INSERT INTO `tb_follow` VALUES (23, 657, 493, '2026-06-13 18:24:17');
INSERT INTO `tb_follow` VALUES (24, 568, 957, '2026-07-17 18:24:17');
INSERT INTO `tb_follow` VALUES (25, 729, 867, '2026-05-25 18:24:17');
INSERT INTO `tb_follow` VALUES (26, 872, 128, '2026-06-24 18:24:17');
INSERT INTO `tb_follow` VALUES (27, 86, 782, '2026-07-10 18:24:17');
INSERT INTO `tb_follow` VALUES (28, 280, 461, '2026-05-26 18:24:17');
INSERT INTO `tb_follow` VALUES (29, 151, 851, '2026-06-05 18:24:17');
INSERT INTO `tb_follow` VALUES (30, 94, 970, '2026-07-02 18:24:17');
INSERT INTO `tb_follow` VALUES (31, 837, 462, '2026-06-16 18:24:17');
INSERT INTO `tb_follow` VALUES (32, 953, 28, '2026-06-07 18:24:17');
INSERT INTO `tb_follow` VALUES (33, 55, 406, '2026-05-27 18:24:17');
INSERT INTO `tb_follow` VALUES (34, 383, 242, '2026-06-11 18:24:17');
INSERT INTO `tb_follow` VALUES (35, 84, 384, '2026-07-02 18:24:17');
INSERT INTO `tb_follow` VALUES (36, 29, 327, '2026-07-18 18:24:17');
INSERT INTO `tb_follow` VALUES (37, 860, 732, '2026-05-08 18:24:17');
INSERT INTO `tb_follow` VALUES (38, 344, 811, '2026-07-12 18:24:17');
INSERT INTO `tb_follow` VALUES (39, 141, 40, '2026-06-24 18:24:17');
INSERT INTO `tb_follow` VALUES (40, 940, 850, '2026-05-31 18:24:17');
INSERT INTO `tb_follow` VALUES (41, 713, 852, '2026-07-13 18:24:17');
INSERT INTO `tb_follow` VALUES (42, 778, 723, '2026-05-31 18:24:17');
INSERT INTO `tb_follow` VALUES (43, 460, 631, '2026-07-30 18:24:17');
INSERT INTO `tb_follow` VALUES (44, 928, 82, '2026-07-28 18:24:17');
INSERT INTO `tb_follow` VALUES (45, 263, 221, '2026-07-11 18:24:17');
INSERT INTO `tb_follow` VALUES (46, 562, 963, '2026-05-14 18:24:17');
INSERT INTO `tb_follow` VALUES (47, 541, 434, '2026-07-16 18:24:17');
INSERT INTO `tb_follow` VALUES (48, 795, 296, '2026-06-30 18:24:17');
INSERT INTO `tb_follow` VALUES (49, 309, 125, '2026-07-24 18:24:17');
INSERT INTO `tb_follow` VALUES (50, 245, 430, '2026-05-10 18:24:17');

-- 共新增 50 条关注关系

-- ===========================================================
-- 7. tb_sign 签到记录
-- ===========================================================

INSERT INTO `tb_sign` VALUES (1, 1, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (2, 1, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (3, 1, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (4, 1, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (5, 1, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (6, 1, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (7, 1, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (8, 1, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (9, 1, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (10, 1, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (11, 1, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (12, 1, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (13, 1, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (14, 1, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (15, 1, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (16, 1, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (17, 1, 2026, 7, '2026-07-15', 0);
INSERT INTO `tb_sign` VALUES (18, 1, 2026, 7, '2026-07-14', 0);
INSERT INTO `tb_sign` VALUES (19, 1, 2026, 7, '2026-07-13', 0);
INSERT INTO `tb_sign` VALUES (20, 2, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (21, 2, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (22, 2, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (23, 2, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (24, 2, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (25, 2, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (26, 2, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (27, 3, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (28, 3, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (29, 3, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (30, 3, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (31, 3, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (32, 3, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (33, 3, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (34, 3, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (35, 4, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (36, 4, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (37, 4, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (38, 4, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (39, 4, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (40, 4, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (41, 4, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (42, 4, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (43, 4, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (44, 4, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (45, 4, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (46, 4, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (47, 4, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (48, 4, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (49, 4, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (50, 4, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (51, 4, 2026, 7, '2026-07-15', 0);
INSERT INTO `tb_sign` VALUES (52, 4, 2026, 7, '2026-07-14', 0);
INSERT INTO `tb_sign` VALUES (53, 4, 2026, 7, '2026-07-13', 0);
INSERT INTO `tb_sign` VALUES (54, 4, 2026, 7, '2026-07-12', 0);
INSERT INTO `tb_sign` VALUES (55, 5, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (56, 5, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (57, 5, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (58, 5, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (59, 5, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (60, 6, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (61, 6, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (62, 6, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (63, 6, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (64, 6, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (65, 6, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (66, 6, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (67, 6, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (68, 6, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (69, 6, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (70, 6, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (71, 6, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (72, 7, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (73, 7, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (74, 7, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (75, 7, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (76, 7, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (77, 7, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (78, 7, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (79, 7, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (80, 7, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (81, 8, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (82, 8, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (83, 8, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (84, 8, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (85, 8, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (86, 8, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (87, 8, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (88, 8, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (89, 8, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (90, 8, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (91, 8, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (92, 8, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (93, 8, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (94, 8, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (95, 9, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (96, 9, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (97, 9, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (98, 9, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (99, 9, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (100, 9, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (101, 9, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (102, 9, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (103, 9, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (104, 9, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (105, 9, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (106, 9, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (107, 9, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (108, 9, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (109, 9, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (110, 9, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (111, 9, 2026, 7, '2026-07-15', 0);
INSERT INTO `tb_sign` VALUES (112, 9, 2026, 7, '2026-07-14', 0);
INSERT INTO `tb_sign` VALUES (113, 10, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (114, 10, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (115, 10, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (116, 10, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (117, 10, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (118, 11, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (119, 11, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (120, 11, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (121, 11, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (122, 11, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (123, 11, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (124, 11, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (125, 11, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (126, 11, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (127, 11, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (128, 11, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (129, 11, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (130, 11, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (131, 11, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (132, 11, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (133, 11, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (134, 12, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (135, 12, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (136, 12, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (137, 12, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (138, 12, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (139, 12, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (140, 12, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (141, 12, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (142, 12, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (143, 12, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (144, 12, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (145, 12, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (146, 13, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (147, 13, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (148, 13, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (149, 13, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (150, 13, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (151, 13, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (152, 13, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (153, 13, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (154, 13, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (155, 13, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (156, 13, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (157, 13, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (158, 13, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (159, 13, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (160, 13, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (161, 13, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (162, 13, 2026, 7, '2026-07-15', 0);
INSERT INTO `tb_sign` VALUES (163, 13, 2026, 7, '2026-07-14', 0);
INSERT INTO `tb_sign` VALUES (164, 14, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (165, 14, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (166, 14, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (167, 14, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (168, 14, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (169, 14, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (170, 14, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (171, 14, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (172, 14, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (173, 14, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (174, 15, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (175, 15, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (176, 15, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (177, 15, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (178, 15, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (179, 15, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (180, 15, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (181, 16, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (182, 16, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (183, 16, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (184, 16, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (185, 16, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (186, 16, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (187, 16, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (188, 16, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (189, 16, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (190, 16, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (191, 16, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (192, 16, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (193, 16, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (194, 16, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (195, 16, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (196, 16, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (197, 17, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (198, 17, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (199, 17, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (200, 17, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (201, 17, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (202, 17, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (203, 17, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (204, 18, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (205, 18, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (206, 18, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (207, 18, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (208, 18, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (209, 19, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (210, 19, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (211, 19, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (212, 19, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (213, 19, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (214, 19, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (215, 19, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (216, 19, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (217, 19, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (218, 19, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (219, 19, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (220, 19, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (221, 19, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (222, 19, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (223, 19, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (224, 19, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (225, 19, 2026, 7, '2026-07-15', 0);
INSERT INTO `tb_sign` VALUES (226, 20, 2026, 7, '2026-07-31', 0);
INSERT INTO `tb_sign` VALUES (227, 20, 2026, 7, '2026-07-30', 0);
INSERT INTO `tb_sign` VALUES (228, 20, 2026, 7, '2026-07-29', 0);
INSERT INTO `tb_sign` VALUES (229, 20, 2026, 7, '2026-07-28', 0);
INSERT INTO `tb_sign` VALUES (230, 20, 2026, 7, '2026-07-27', 0);
INSERT INTO `tb_sign` VALUES (231, 20, 2026, 7, '2026-07-26', 0);
INSERT INTO `tb_sign` VALUES (232, 20, 2026, 7, '2026-07-25', 0);
INSERT INTO `tb_sign` VALUES (233, 20, 2026, 7, '2026-07-24', 0);
INSERT INTO `tb_sign` VALUES (234, 20, 2026, 7, '2026-07-23', 0);
INSERT INTO `tb_sign` VALUES (235, 20, 2026, 7, '2026-07-22', 0);
INSERT INTO `tb_sign` VALUES (236, 20, 2026, 7, '2026-07-21', 0);
INSERT INTO `tb_sign` VALUES (237, 20, 2026, 7, '2026-07-20', 0);
INSERT INTO `tb_sign` VALUES (238, 20, 2026, 7, '2026-07-19', 0);
INSERT INTO `tb_sign` VALUES (239, 20, 2026, 7, '2026-07-18', 0);
INSERT INTO `tb_sign` VALUES (240, 20, 2026, 7, '2026-07-17', 0);
INSERT INTO `tb_sign` VALUES (241, 20, 2026, 7, '2026-07-16', 0);
INSERT INTO `tb_sign` VALUES (242, 20, 2026, 7, '2026-07-15', 0);
INSERT INTO `tb_sign` VALUES (243, 20, 2026, 7, '2026-07-14', 0);
INSERT INTO `tb_sign` VALUES (244, 20, 2026, 7, '2026-07-13', 0);
INSERT INTO `tb_sign` VALUES (245, 20, 2026, 7, '2026-07-12', 0);

-- 共新增 245 条签到记录

-- ===========================================================
-- 8. tb_user_info 用户详细信息
-- ===========================================================

INSERT INTO `tb_user_info` VALUES (1, '杭州', '美食探店博主', 191, 64, 0, '1996-02-12', 1975, 5, '2025-08-14 18:24:17', '2025-08-14 18:24:17');
INSERT INTO `tb_user_info` VALUES (2, '上海', '运动达人', 376, 193, 1, '1989-01-12', 4472, 2, '2025-08-06 18:24:17', '2025-08-06 18:24:17');
INSERT INTO `tb_user_info` VALUES (3, '北京', '杭州本地通', 356, 122, 0, '1989-02-23', 3749, 0, '2026-02-01 18:24:17', '2026-02-01 18:24:17');
INSERT INTO `tb_user_info` VALUES (4, '深圳', '美食爱好者', 405, 51, 0, '1995-05-17', 3262, 4, '2025-11-01 18:24:17', '2025-11-01 18:24:17');
INSERT INTO `tb_user_info` VALUES (5, '广州', '美食爱好者', 385, 165, 0, '1994-06-28', 391, 5, '2026-01-13 18:24:17', '2026-01-13 18:24:17');
INSERT INTO `tb_user_info` VALUES (6, '广州', '热爱生活', 409, 94, 1, '1997-12-15', 3167, 2, '2026-03-28 18:24:17', '2026-03-28 18:24:17');
INSERT INTO `tb_user_info` VALUES (7, '苏州', '杭州本地通', 188, 132, 1, '1987-12-14', 646, 3, '2025-08-27 18:24:17', '2025-08-27 18:24:17');
INSERT INTO `tb_user_info` VALUES (8, '北京', '文艺青年', 150, 82, 0, '1987-06-22', 2421, 2, '2025-11-15 18:24:17', '2025-11-15 18:24:17');
INSERT INTO `tb_user_info` VALUES (9, '南京', '旅行达人', 353, 113, 1, '1999-01-24', 2888, 4, '2025-11-21 18:24:17', '2025-11-21 18:24:17');
INSERT INTO `tb_user_info` VALUES (10, '广州', '美食爱好者', 38, 171, 1, '1996-09-26', 1310, 0, '2026-04-19 18:24:17', '2026-04-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (11, '苏州', '美食爱好者', 64, 17, 0, '1996-06-13', 4646, 0, '2025-08-26 18:24:17', '2025-08-26 18:24:17');
INSERT INTO `tb_user_info` VALUES (12, '北京', '杭州本地通', 485, 94, 1, '1999-02-19', 1127, 4, '2025-12-26 18:24:17', '2025-12-26 18:24:17');
INSERT INTO `tb_user_info` VALUES (13, '南京', '享受每一天', 332, 71, 0, '1988-01-24', 1524, 3, '2025-10-09 18:24:17', '2025-10-09 18:24:17');
INSERT INTO `tb_user_info` VALUES (14, '南京', '文艺青年', 60, 67, 1, '1999-04-20', 2339, 5, '2025-10-23 18:24:17', '2025-10-23 18:24:17');
INSERT INTO `tb_user_info` VALUES (15, '深圳', '热爱生活', 69, 18, 1, '1990-12-15', 719, 5, '2026-01-19 18:24:17', '2026-01-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (16, '成都', '热爱生活', 281, 138, 1, '1994-03-23', 1426, 2, '2025-10-14 18:24:17', '2025-10-14 18:24:17');
INSERT INTO `tb_user_info` VALUES (17, '深圳', '热爱生活', 102, 35, 0, '2000-01-12', 4538, 4, '2025-12-25 18:24:17', '2025-12-25 18:24:17');
INSERT INTO `tb_user_info` VALUES (18, '苏州', '文艺青年', 66, 156, 0, '1987-05-13', 3921, 4, '2025-12-03 18:24:17', '2025-12-03 18:24:17');
INSERT INTO `tb_user_info` VALUES (19, '南京', '运动达人', 37, 32, 1, '1987-08-15', 4238, 2, '2026-04-27 18:24:17', '2026-04-27 18:24:17');
INSERT INTO `tb_user_info` VALUES (20, '北京', '旅行达人', 221, 128, 0, '1988-09-05', 2491, 1, '2026-04-10 18:24:17', '2026-04-10 18:24:17');
INSERT INTO `tb_user_info` VALUES (21, '成都', '吃货一枚', 177, 132, 1, '1987-05-07', 4512, 2, '2026-04-28 18:24:17', '2026-04-28 18:24:17');
INSERT INTO `tb_user_info` VALUES (22, '广州', '运动达人', 273, 23, 0, '1989-03-22', 4957, 2, '2025-09-16 18:24:17', '2025-09-16 18:24:17');
INSERT INTO `tb_user_info` VALUES (23, '杭州', '美食爱好者', 41, 11, 1, '1991-10-14', 248, 3, '2025-08-14 18:24:17', '2025-08-14 18:24:17');
INSERT INTO `tb_user_info` VALUES (24, '广州', '生活探索者', 247, 62, 1, '1994-08-03', 490, 1, '2025-11-18 18:24:17', '2025-11-18 18:24:17');
INSERT INTO `tb_user_info` VALUES (25, '南京', '杭州本地通', 237, 52, 1, '1989-06-28', 2615, 5, '2026-01-06 18:24:17', '2026-01-06 18:24:17');
INSERT INTO `tb_user_info` VALUES (26, '南京', '旅行达人', 389, 94, 0, '1995-04-15', 1003, 2, '2025-11-13 18:24:17', '2025-11-13 18:24:17');
INSERT INTO `tb_user_info` VALUES (27, '深圳', '旅行达人', 49, 12, 1, '1997-10-14', 2033, 1, '2026-01-15 18:24:17', '2026-01-15 18:24:17');
INSERT INTO `tb_user_info` VALUES (28, '成都', '吃货一枚', 390, 40, 1, '1999-08-10', 4074, 0, '2026-05-16 18:24:17', '2026-05-16 18:24:17');
INSERT INTO `tb_user_info` VALUES (29, '南京', '文艺青年', 234, 61, 0, '1996-01-02', 2304, 3, '2025-08-30 18:24:17', '2025-08-30 18:24:17');
INSERT INTO `tb_user_info` VALUES (30, '苏州', '生活探索者', 274, 2, 0, '1998-03-09', 2996, 3, '2025-12-26 18:24:17', '2025-12-26 18:24:17');
INSERT INTO `tb_user_info` VALUES (31, '杭州', '美食探店博主', 26, 145, 0, '1996-09-10', 602, 3, '2025-10-16 18:24:17', '2025-10-16 18:24:17');
INSERT INTO `tb_user_info` VALUES (32, '苏州', '文艺青年', 143, 159, 0, '1989-02-13', 3057, 2, '2025-09-19 18:24:17', '2025-09-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (33, '成都', '旅行达人', 101, 154, 1, '1986-01-02', 1122, 5, '2026-01-12 18:24:17', '2026-01-12 18:24:17');
INSERT INTO `tb_user_info` VALUES (34, '苏州', '文艺青年', 233, 38, 0, '1995-10-11', 1331, 3, '2025-08-20 18:24:17', '2025-08-20 18:24:17');
INSERT INTO `tb_user_info` VALUES (35, '广州', '运动达人', 172, 129, 1, '1994-08-27', 136, 2, '2026-01-13 18:24:17', '2026-01-13 18:24:17');
INSERT INTO `tb_user_info` VALUES (36, '上海', '美食探店博主', 298, 78, 0, '2000-05-21', 4738, 4, '2026-03-07 18:24:17', '2026-03-07 18:24:17');
INSERT INTO `tb_user_info` VALUES (37, '杭州', '运动达人', 245, 43, 1, '1989-11-08', 258, 4, '2026-05-06 18:24:17', '2026-05-06 18:24:17');
INSERT INTO `tb_user_info` VALUES (38, '深圳', '美食爱好者', 225, 80, 1, '1989-07-23', 1670, 3, '2025-10-18 18:24:17', '2025-10-18 18:24:17');
INSERT INTO `tb_user_info` VALUES (39, '苏州', '美食爱好者', 361, 35, 0, '1995-11-16', 4304, 3, '2026-01-22 18:24:17', '2026-01-22 18:24:17');
INSERT INTO `tb_user_info` VALUES (40, '北京', '杭州本地通', 467, 136, 1, '1996-11-25', 2165, 4, '2025-10-27 18:24:17', '2025-10-27 18:24:17');
INSERT INTO `tb_user_info` VALUES (41, '深圳', '吃货一枚', 142, 142, 1, '1992-05-25', 2367, 5, '2026-03-17 18:24:17', '2026-03-17 18:24:17');
INSERT INTO `tb_user_info` VALUES (42, '苏州', '享受每一天', 245, 89, 1, '1994-02-19', 4449, 3, '2025-12-11 18:24:17', '2025-12-11 18:24:17');
INSERT INTO `tb_user_info` VALUES (43, '成都', '旅行达人', 148, 10, 1, '1987-06-15', 2100, 5, '2025-10-29 18:24:17', '2025-10-29 18:24:17');
INSERT INTO `tb_user_info` VALUES (44, '深圳', '吃货一枚', 423, 137, 1, '1993-03-04', 4807, 1, '2026-02-27 18:24:17', '2026-02-27 18:24:17');
INSERT INTO `tb_user_info` VALUES (45, '杭州', '文艺青年', 115, 163, 0, '1986-02-14', 2705, 5, '2025-11-02 18:24:17', '2025-11-02 18:24:17');
INSERT INTO `tb_user_info` VALUES (46, '上海', '旅行达人', 2, 140, 0, '1998-11-16', 3911, 5, '2026-03-21 18:24:17', '2026-03-21 18:24:17');
INSERT INTO `tb_user_info` VALUES (47, '广州', '享受每一天', 146, 165, 0, '1987-11-19', 1902, 4, '2026-06-12 18:24:17', '2026-06-12 18:24:17');
INSERT INTO `tb_user_info` VALUES (48, '北京', '美食探店博主', 451, 45, 0, '1997-08-06', 2371, 0, '2026-06-27 18:24:17', '2026-06-27 18:24:17');
INSERT INTO `tb_user_info` VALUES (49, '广州', '运动达人', 308, 27, 1, '1994-08-21', 4450, 4, '2025-10-22 18:24:17', '2025-10-22 18:24:17');
INSERT INTO `tb_user_info` VALUES (50, '北京', '文艺青年', 239, 69, 0, '1988-06-06', 3759, 5, '2026-02-20 18:24:17', '2026-02-20 18:24:17');
INSERT INTO `tb_user_info` VALUES (51, '北京', '美食爱好者', 377, 86, 1, '1991-03-20', 3321, 3, '2025-10-11 18:24:17', '2025-10-11 18:24:17');
INSERT INTO `tb_user_info` VALUES (52, '成都', '热爱生活', 205, 171, 0, '1990-03-16', 2650, 1, '2026-06-28 18:24:17', '2026-06-28 18:24:17');
INSERT INTO `tb_user_info` VALUES (53, '广州', '美食探店博主', 120, 114, 1, '1995-05-19', 4693, 0, '2026-02-18 18:24:17', '2026-02-18 18:24:17');
INSERT INTO `tb_user_info` VALUES (54, '成都', '吃货一枚', 31, 170, 0, '1999-05-06', 3321, 5, '2025-10-17 18:24:17', '2025-10-17 18:24:17');
INSERT INTO `tb_user_info` VALUES (55, '广州', '热爱生活', 327, 75, 1, '1992-04-05', 3917, 1, '2025-11-11 18:24:17', '2025-11-11 18:24:17');
INSERT INTO `tb_user_info` VALUES (56, '成都', '美食探店博主', 359, 140, 1, '1991-04-22', 4880, 0, '2025-10-05 18:24:17', '2025-10-05 18:24:17');
INSERT INTO `tb_user_info` VALUES (57, '苏州', '文艺青年', 360, 92, 0, '1988-01-27', 4486, 4, '2026-03-20 18:24:17', '2026-03-20 18:24:17');
INSERT INTO `tb_user_info` VALUES (58, '北京', '旅行达人', 167, 133, 1, '1988-11-07', 4777, 3, '2026-05-16 18:24:17', '2026-05-16 18:24:17');
INSERT INTO `tb_user_info` VALUES (59, '苏州', '美食爱好者', 232, 33, 1, '1999-10-02', 4577, 3, '2026-01-25 18:24:17', '2026-01-25 18:24:17');
INSERT INTO `tb_user_info` VALUES (60, '杭州', '美食探店博主', 130, 0, 0, '1987-01-14', 2822, 5, '2026-05-30 18:24:17', '2026-05-30 18:24:17');
INSERT INTO `tb_user_info` VALUES (61, '杭州', '热爱生活', 478, 120, 0, '1994-07-06', 1109, 5, '2025-08-05 18:24:17', '2025-08-05 18:24:17');
INSERT INTO `tb_user_info` VALUES (62, '南京', '享受每一天', 456, 97, 1, '1997-07-03', 4417, 1, '2025-08-01 18:24:17', '2025-08-01 18:24:17');
INSERT INTO `tb_user_info` VALUES (63, '成都', '热爱生活', 91, 137, 1, '1989-12-08', 28, 0, '2026-01-30 18:24:17', '2026-01-30 18:24:17');
INSERT INTO `tb_user_info` VALUES (64, '苏州', '文艺青年', 217, 136, 1, '1992-04-15', 2835, 1, '2026-02-10 18:24:17', '2026-02-10 18:24:17');
INSERT INTO `tb_user_info` VALUES (65, '深圳', '热爱生活', 16, 169, 1, '1985-04-07', 551, 0, '2025-08-31 18:24:17', '2025-08-31 18:24:17');
INSERT INTO `tb_user_info` VALUES (66, '杭州', '杭州本地通', 306, 172, 0, '1992-12-02', 3295, 3, '2026-03-04 18:24:17', '2026-03-04 18:24:17');
INSERT INTO `tb_user_info` VALUES (67, '深圳', '美食爱好者', 71, 128, 1, '1992-12-19', 2612, 4, '2025-08-29 18:24:17', '2025-08-29 18:24:17');
INSERT INTO `tb_user_info` VALUES (68, '成都', '吃货一枚', 154, 36, 0, '1998-05-09', 499, 4, '2025-09-02 18:24:17', '2025-09-02 18:24:17');
INSERT INTO `tb_user_info` VALUES (69, '北京', '美食探店博主', 284, 126, 0, '1996-11-22', 3122, 4, '2026-01-19 18:24:17', '2026-01-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (70, '南京', '美食探店博主', 76, 76, 1, '1990-09-16', 1974, 1, '2026-01-29 18:24:17', '2026-01-29 18:24:17');
INSERT INTO `tb_user_info` VALUES (71, '北京', '杭州本地通', 468, 14, 1, '1998-09-17', 1098, 3, '2026-02-27 18:24:17', '2026-02-27 18:24:17');
INSERT INTO `tb_user_info` VALUES (72, '广州', '吃货一枚', 169, 165, 0, '1999-06-03', 4387, 5, '2026-03-26 18:24:17', '2026-03-26 18:24:17');
INSERT INTO `tb_user_info` VALUES (73, '杭州', '生活探索者', 193, 172, 0, '1987-04-26', 4813, 5, '2025-09-18 18:24:17', '2025-09-18 18:24:17');
INSERT INTO `tb_user_info` VALUES (74, '深圳', '杭州本地通', 106, 85, 1, '1985-04-07', 961, 5, '2025-10-29 18:24:17', '2025-10-29 18:24:17');
INSERT INTO `tb_user_info` VALUES (75, '深圳', '运动达人', 360, 52, 1, '1992-09-11', 2318, 3, '2025-11-05 18:24:17', '2025-11-05 18:24:17');
INSERT INTO `tb_user_info` VALUES (76, '成都', '生活探索者', 133, 92, 1, '1999-02-26', 3846, 2, '2026-03-19 18:24:17', '2026-03-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (77, '成都', '享受每一天', 211, 11, 0, '1989-01-09', 4532, 4, '2025-09-08 18:24:17', '2025-09-08 18:24:17');
INSERT INTO `tb_user_info` VALUES (78, '南京', '生活探索者', 78, 50, 1, '1992-07-19', 2013, 3, '2025-09-23 18:24:17', '2025-09-23 18:24:17');
INSERT INTO `tb_user_info` VALUES (79, '成都', '生活探索者', 390, 125, 1, '1999-03-24', 2885, 1, '2026-04-21 18:24:17', '2026-04-21 18:24:17');
INSERT INTO `tb_user_info` VALUES (80, '苏州', '旅行达人', 469, 138, 0, '1986-02-27', 397, 0, '2025-12-02 18:24:17', '2025-12-02 18:24:17');
INSERT INTO `tb_user_info` VALUES (81, '北京', '吃货一枚', 34, 181, 0, '1985-04-17', 3735, 2, '2026-06-01 18:24:17', '2026-06-01 18:24:17');
INSERT INTO `tb_user_info` VALUES (82, '苏州', '杭州本地通', 8, 1, 1, '1985-01-17', 2250, 4, '2026-02-05 18:24:17', '2026-02-05 18:24:17');
INSERT INTO `tb_user_info` VALUES (83, '杭州', '文艺青年', 416, 178, 1, '1990-02-04', 4295, 1, '2026-02-28 18:24:17', '2026-02-28 18:24:17');
INSERT INTO `tb_user_info` VALUES (84, '深圳', '运动达人', 269, 64, 1, '1993-07-03', 3056, 3, '2025-11-08 18:24:17', '2025-11-08 18:24:17');
INSERT INTO `tb_user_info` VALUES (85, '深圳', '吃货一枚', 153, 175, 0, '1986-02-13', 3106, 3, '2025-09-22 18:24:17', '2025-09-22 18:24:17');
INSERT INTO `tb_user_info` VALUES (86, '苏州', '美食爱好者', 326, 2, 0, '1987-08-28', 3554, 5, '2026-01-13 18:24:17', '2026-01-13 18:24:17');
INSERT INTO `tb_user_info` VALUES (87, '上海', '文艺青年', 470, 10, 0, '1991-12-19', 3895, 2, '2026-06-08 18:24:17', '2026-06-08 18:24:17');
INSERT INTO `tb_user_info` VALUES (88, '上海', '生活探索者', 460, 139, 0, '1990-06-01', 1697, 4, '2026-04-19 18:24:17', '2026-04-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (89, '南京', '热爱生活', 153, 41, 0, '1997-11-18', 2717, 3, '2026-04-21 18:24:17', '2026-04-21 18:24:17');
INSERT INTO `tb_user_info` VALUES (90, '上海', '文艺青年', 381, 88, 0, '1988-07-08', 622, 2, '2025-08-26 18:24:17', '2025-08-26 18:24:17');
INSERT INTO `tb_user_info` VALUES (91, '南京', '享受每一天', 15, 162, 1, '1999-08-08', 2914, 4, '2025-12-21 18:24:17', '2025-12-21 18:24:17');
INSERT INTO `tb_user_info` VALUES (92, '南京', '旅行达人', 348, 149, 1, '1987-10-10', 2018, 5, '2026-05-25 18:24:17', '2026-05-25 18:24:17');
INSERT INTO `tb_user_info` VALUES (93, '上海', '生活探索者', 78, 97, 0, '1997-06-12', 872, 0, '2026-06-29 18:24:17', '2026-06-29 18:24:17');
INSERT INTO `tb_user_info` VALUES (94, '广州', '杭州本地通', 184, 194, 1, '1988-03-03', 1535, 3, '2025-11-14 18:24:17', '2025-11-14 18:24:17');
INSERT INTO `tb_user_info` VALUES (95, '南京', '热爱生活', 13, 22, 1, '1987-10-20', 2657, 3, '2026-06-25 18:24:17', '2026-06-25 18:24:17');
INSERT INTO `tb_user_info` VALUES (96, '广州', '美食探店博主', 198, 199, 0, '1992-10-17', 1389, 5, '2025-12-19 18:24:17', '2025-12-19 18:24:17');
INSERT INTO `tb_user_info` VALUES (97, '北京', '旅行达人', 137, 77, 1, '2000-03-03', 1369, 3, '2026-02-10 18:24:17', '2026-02-10 18:24:17');
INSERT INTO `tb_user_info` VALUES (98, '南京', '生活探索者', 247, 200, 0, '1996-05-08', 4061, 4, '2025-08-20 18:24:17', '2025-08-20 18:24:17');
INSERT INTO `tb_user_info` VALUES (99, '深圳', '杭州本地通', 54, 34, 1, '1985-07-11', 3112, 2, '2025-11-18 18:24:17', '2025-11-18 18:24:17');
INSERT INTO `tb_user_info` VALUES (100, '成都', '美食探店博主', 417, 166, 0, '1994-06-20', 1645, 3, '2026-01-22 18:24:17', '2026-01-22 18:24:17');

-- 共100条用户信息

-- ===========================================================
-- 9. tb_voucher_order 优惠券订单
-- ===========================================================

INSERT INTO `tb_voucher_order` VALUES (1700000000000000001, 182, 2, 1, 3, '2026-07-20 18:24:17', '2026-07-20 18:24:17', '2026-07-29 18:24:17', NULL, '2026-07-20 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000002, 753, 3, 1, 3, '2026-07-12 18:24:17', '2026-07-12 18:24:17', '2026-07-30 18:24:17', NULL, '2026-07-12 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000003, 334, 4, 1, 3, '2026-07-22 18:24:17', '2026-07-22 18:24:17', '2026-07-28 18:24:17', NULL, '2026-07-22 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000004, 374, 5, 1, 2, '2026-07-01 18:24:17', '2026-07-01 18:24:17', NULL, NULL, '2026-07-01 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000005, 578, 6, 1, 2, '2026-07-12 18:24:17', '2026-07-12 18:24:17', NULL, NULL, '2026-07-12 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000006, 559, 7, 1, 2, '2026-07-09 18:24:17', '2026-07-09 18:24:17', NULL, NULL, '2026-07-09 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000007, 787, 8, 1, 2, '2026-07-07 18:24:17', '2026-07-07 18:24:17', NULL, NULL, '2026-07-07 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000008, 473, 9, 1, 2, '2026-07-16 18:24:17', '2026-07-16 18:24:17', NULL, NULL, '2026-07-16 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000009, 817, 10, 1, 3, '2026-07-04 18:24:17', '2026-07-04 18:24:17', '2026-07-26 18:24:17', NULL, '2026-07-04 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000010, 71, 11, 1, 3, '2026-07-09 18:24:17', '2026-07-09 18:24:17', '2026-07-28 18:24:17', NULL, '2026-07-09 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000011, 143, 32, 3, 2, '2026-07-31 03:24:17', '2026-07-31 10:24:17', NULL, NULL, '2026-07-31 03:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000012, 158, 32, 3, 3, '2026-07-30 18:24:17', '2026-07-31 16:24:17', '2026-07-31 11:24:17', NULL, '2026-07-30 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000013, 491, 32, 2, 3, '2026-07-30 08:24:17', '2026-07-31 02:24:17', '2026-07-31 07:24:17', NULL, '2026-07-30 08:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000014, 557, 32, 3, 1, '2026-07-30 19:24:17', NULL, NULL, NULL, '2026-07-30 19:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000015, 917, 32, 1, 1, '2026-07-31 12:24:17', NULL, NULL, NULL, '2026-07-31 12:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000016, 674, 33, 3, 2, '2026-07-31 08:24:17', '2026-07-30 22:24:17', NULL, NULL, '2026-07-31 08:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000017, 46, 33, 2, 3, '2026-07-29 18:24:17', '2026-07-31 08:24:17', '2026-07-31 06:24:17', NULL, '2026-07-29 18:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000018, 109, 33, 2, 1, '2026-07-31 12:24:17', NULL, NULL, NULL, '2026-07-31 12:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000019, 228, 33, 2, 2, '2026-07-30 14:24:17', '2026-07-31 07:24:17', NULL, NULL, '2026-07-30 14:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000020, 475, 33, 2, 2, '2026-07-30 20:24:17', '2026-07-31 18:24:17', NULL, NULL, '2026-07-30 20:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000021, 108, 34, 1, 2, '2026-07-30 16:24:17', '2026-07-31 16:24:17', NULL, NULL, '2026-07-30 16:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000022, 852, 34, 2, 2, '2026-07-30 20:24:17', '2026-07-31 09:24:17', NULL, NULL, '2026-07-30 20:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000023, 467, 34, 2, 2, '2026-07-30 09:24:17', '2026-07-31 03:24:17', NULL, NULL, '2026-07-30 09:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000024, 488, 34, 3, 1, '2026-07-30 14:24:17', NULL, NULL, NULL, '2026-07-30 14:24:17');
INSERT INTO `tb_voucher_order` VALUES (1700000000000000025, 714, 34, 1, 3, '2026-07-30 22:24:17', '2026-07-31 16:24:17', '2026-07-31 14:24:17', NULL, '2026-07-30 22:24:17');

-- 共新增 25 条订单

-- ===========================================================
-- 10. tb_pay_log 支付流水
-- ===========================================================

INSERT INTO `tb_pay_log` VALUES (1, 1700000000000000001, 830, 3, '4200125426700679782', 5000, 2, '2026-07-26 18:24:17', '2026-07-26 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (2, 1700000000000000002, 953, 3, '4200680955503924275', 9500, 2, '2026-07-21 18:24:17', '2026-07-21 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (3, 1700000000000000003, 574, 2, '4200620227735326317', 9500, 4, '2026-07-11 18:24:17', '2026-07-11 18:24:17', '2026-07-30 18:24:17');
INSERT INTO `tb_pay_log` VALUES (4, 1700000000000000004, 191, 3, '4200586541013374147', 10000, 2, '2026-07-12 18:24:17', '2026-07-12 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (5, 1700000000000000005, 905, 1, '4200766761243875610', 10000, 4, '2026-07-31 18:24:17', '2026-07-31 18:24:17', '2026-07-26 18:24:17');
INSERT INTO `tb_pay_log` VALUES (6, 1700000000000000006, 220, 1, '4200947041760697160', 4750, 2, '2026-07-14 18:24:17', '2026-07-14 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (7, 1700000000000000007, 192, 2, '4200321883705573197', 10000, 2, '2026-07-23 18:24:17', '2026-07-23 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (8, 1700000000000000008, 687, 2, '4200452864373087942', 2500, 4, '2026-07-12 18:24:17', '2026-07-12 18:24:17', '2026-07-28 18:24:17');
INSERT INTO `tb_pay_log` VALUES (9, 1700000000000000009, 602, 1, '4200496298126726876', 10000, 2, '2026-07-22 18:24:17', '2026-07-22 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (10, 1700000000000000010, 941, 3, '4200195423823169075', 9500, 2, '2026-07-28 18:24:17', '2026-07-28 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (11, 1700000000000000011, 245, 2, '4200306090213023000', 5000, 2, '2026-07-15 18:24:17', '2026-07-15 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (12, 1700000000000000012, 398, 2, '4200255226974674122', 2500, 4, '2026-07-18 18:24:17', '2026-07-18 18:24:17', '2026-07-30 18:24:17');
INSERT INTO `tb_pay_log` VALUES (13, 1700000000000000013, 499, 3, '4200880737168125978', 9500, 2, '2026-07-16 18:24:17', '2026-07-16 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (14, 1700000000000000014, 296, 1, '4200454185281646912', 10000, 2, '2026-07-20 18:24:17', '2026-07-20 18:24:17', NULL);
INSERT INTO `tb_pay_log` VALUES (15, 1700000000000000015, 975, 1, '4200253723255870621', 9500, 4, '2026-07-14 18:24:17', '2026-07-14 18:24:17', '2026-07-27 18:24:17');

-- 共新增 15 条支付流水

-- ===========================================================
-- 11. 更新新商铺的 tags 字段（用于 ES 全文搜索）
-- ===========================================================
-- 注意：此步骤需要先执行 sql/upgrade_payment_and_search.sql
-- 如果未执行该迁移脚本，以下语句会报错但可忽略

UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,口碑好,性价比' WHERE `id` = 15;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,服务佳,性价比' WHERE `id` = 16;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,服务佳,网红店' WHERE `id` = 17;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,环境好,性价比' WHERE `id` = 18;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,服务佳,环境好' WHERE `id` = 19;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,老字号,环境好' WHERE `id` = 20;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,性价比,环境好' WHERE `id` = 21;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,老字号,口碑好' WHERE `id` = 22;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,环境好,老字号' WHERE `id` = 23;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,性价比,口碑好' WHERE `id` = 24;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,老字号,服务佳' WHERE `id` = 25;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,性价比,服务佳' WHERE `id` = 26;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,性价比,老字号' WHERE `id` = 27;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,老字号,口碑好' WHERE `id` = 28;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,老字号,服务佳' WHERE `id` = 29;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,性价比,老字号' WHERE `id` = 30;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,网红店,环境好' WHERE `id` = 31;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,口碑好,老字号' WHERE `id` = 32;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,性价比,环境好' WHERE `id` = 33;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,网红店,性价比' WHERE `id` = 34;
UPDATE `tb_shop` SET `tags` = '美食,好吃,推荐,热门,口碑好,环境好' WHERE `id` = 35;
UPDATE `tb_shop` SET `tags` = 'KTV,唱歌,聚会,娱乐,环境好,服务佳' WHERE `id` = 36;
UPDATE `tb_shop` SET `tags` = 'KTV,唱歌,聚会,娱乐,网红店,性价比' WHERE `id` = 37;
UPDATE `tb_shop` SET `tags` = 'KTV,唱歌,聚会,娱乐,性价比,口碑好' WHERE `id` = 38;
UPDATE `tb_shop` SET `tags` = 'KTV,唱歌,聚会,娱乐,环境好,服务佳' WHERE `id` = 39;
UPDATE `tb_shop` SET `tags` = 'KTV,唱歌,聚会,娱乐,服务佳,环境好' WHERE `id` = 40;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,网红店,服务佳' WHERE `id` = 41;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,服务佳,环境好' WHERE `id` = 42;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,服务佳,环境好' WHERE `id` = 43;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,老字号,环境好' WHERE `id` = 44;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,性价比,服务佳' WHERE `id` = 45;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,环境好,口碑好' WHERE `id` = 46;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,老字号,性价比' WHERE `id` = 47;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,老字号,环境好' WHERE `id` = 48;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,性价比,老字号' WHERE `id` = 49;
UPDATE `tb_shop` SET `tags` = '美发,造型,烫染,时尚,网红店,老字号' WHERE `id` = 50;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,口碑好,性价比' WHERE `id` = 51;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,服务佳,网红店' WHERE `id` = 52;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,服务佳,环境好' WHERE `id` = 53;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,性价比,服务佳' WHERE `id` = 54;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,性价比,环境好' WHERE `id` = 55;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,口碑好,环境好' WHERE `id` = 56;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,网红店,环境好' WHERE `id` = 57;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,环境好,口碑好' WHERE `id` = 58;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,老字号,服务佳' WHERE `id` = 59;
UPDATE `tb_shop` SET `tags` = '健身,运动,游泳,瑜伽,环境好,性价比' WHERE `id` = 60;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,网红店,口碑好' WHERE `id` = 61;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,口碑好,老字号' WHERE `id` = 62;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,口碑好,网红店' WHERE `id` = 63;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,环境好,口碑好' WHERE `id` = 64;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,网红店,性价比' WHERE `id` = 65;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,性价比,网红店' WHERE `id` = 66;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,网红店,性价比' WHERE `id` = 67;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,网红店,环境好' WHERE `id` = 68;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,服务佳,性价比' WHERE `id` = 69;
UPDATE `tb_shop` SET `tags` = '按摩,足疗,推拿,养生,环境好,口碑好' WHERE `id` = 70;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,环境好,性价比' WHERE `id` = 71;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,服务佳,环境好' WHERE `id` = 72;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,环境好,性价比' WHERE `id` = 73;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,服务佳,环境好' WHERE `id` = 74;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,老字号,口碑好' WHERE `id` = 75;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,口碑好,服务佳' WHERE `id` = 76;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,老字号,网红店' WHERE `id` = 77;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,服务佳,口碑好' WHERE `id` = 78;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,网红店,性价比' WHERE `id` = 79;
UPDATE `tb_shop` SET `tags` = 'SPA,美容,护肤,放松,网红店,口碑好' WHERE `id` = 80;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,环境好,老字号' WHERE `id` = 81;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,网红店,口碑好' WHERE `id` = 82;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,性价比,网红店' WHERE `id` = 83;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,性价比,口碑好' WHERE `id` = 84;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,口碑好,服务佳' WHERE `id` = 85;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,环境好,口碑好' WHERE `id` = 86;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,服务佳,老字号' WHERE `id` = 87;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,服务佳,老字号' WHERE `id` = 88;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,网红店,服务佳' WHERE `id` = 89;
UPDATE `tb_shop` SET `tags` = '亲子,儿童,乐园,家庭,老字号,口碑好' WHERE `id` = 90;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,口碑好,性价比' WHERE `id` = 91;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,口碑好,老字号' WHERE `id` = 92;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,网红店,服务佳' WHERE `id` = 93;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,服务佳,网红店' WHERE `id` = 94;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,服务佳,口碑好' WHERE `id` = 95;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,性价比,口碑好' WHERE `id` = 96;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,网红店,口碑好' WHERE `id` = 97;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,网红店,性价比' WHERE `id` = 98;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,环境好,服务佳' WHERE `id` = 99;
UPDATE `tb_shop` SET `tags` = '酒吧,夜生活,音乐,聚会,老字号,环境好' WHERE `id` = 100;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,服务佳,口碑好' WHERE `id` = 101;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,服务佳,网红店' WHERE `id` = 102;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,口碑好,网红店' WHERE `id` = 103;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,网红店,口碑好' WHERE `id` = 104;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,老字号,性价比' WHERE `id` = 105;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,环境好,老字号' WHERE `id` = 106;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,性价比,口碑好' WHERE `id` = 107;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,网红店,性价比' WHERE `id` = 108;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,性价比,网红店' WHERE `id` = 109;
UPDATE `tb_shop` SET `tags` = '轰趴,聚会,派对,团建,口碑好,性价比' WHERE `id` = 110;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,口碑好,服务佳' WHERE `id` = 111;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,服务佳,性价比' WHERE `id` = 112;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,口碑好,服务佳' WHERE `id` = 113;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,环境好,网红店' WHERE `id` = 114;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,环境好,老字号' WHERE `id` = 115;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,服务佳,性价比' WHERE `id` = 116;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,网红店,性价比' WHERE `id` = 117;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,口碑好,老字号' WHERE `id` = 118;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,环境好,服务佳' WHERE `id` = 119;
UPDATE `tb_shop` SET `tags` = '美甲,美睫,美容,时尚,老字号,性价比' WHERE `id` = 120;

-- 共更新 106 家商铺的 tags 字段

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- 数据生成完毕
-- 新增商铺: 106 家 (ID 15~120)
-- 新增优惠券: 33 张 (含秒杀券)
-- 新增探店笔记: 20 条
-- 新增评论: 32 条
-- 新增关注: 50 条
-- 新增签到: 245 条
-- 新增用户信息: 100 条
-- 新增订单: 25 条
-- 新增支付流水: 15 条
-- =====================================================================