-- Human-readable definitions used by LLM classification prompts and review UI.

ALTER TABLE capability_directions ADD COLUMN description TEXT;
ALTER TABLE capability_categories ADD COLUMN description TEXT;

UPDATE capability_directions SET description =
    '面向组织长期目标、业务方向和资源配置的决策与管理能力，包括战略规划、运营管理和项目资源统筹。'
WHERE code = 'CD1';
UPDATE capability_directions SET description =
    '面向具身智能基础理论、前沿技术、算法方法和系统方案的研究、设计与验证能力。'
WHERE code = 'CD2';
UPDATE capability_directions SET description =
    '将算法和产品方案实现为可运行软硬件系统的工程能力，包括软件、硬件、集成、部署和运维。'
WHERE code = 'CD3';
UPDATE capability_directions SET description =
    '保障产品可验证、可制造、可交付和质量稳定的能力，包括测试、生产工艺、质量和供应链。'
WHERE code = 'CD4';
UPDATE capability_directions SET description =
    '推动具身智能产品进入市场并持续服务客户的能力，包括市场、销售、解决方案、交付和技术服务。'
WHERE code = 'CD5';
UPDATE capability_directions SET description =
    '保障组织稳定运行的专业支撑能力，包括人力资源、财务、法务、合规、行政和知识产权。'
WHERE code = 'CD6';

UPDATE capability_categories SET description =
    '识别长期趋势和关键问题，制定组织、产品或技术战略并作出重要业务决策的能力。'
WHERE code = 'C1.1';
UPDATE capability_categories SET description =
    '设计组织机制、业务流程和运营体系，推动跨部门协作和持续改进的能力。'
WHERE code = 'C1.2';
UPDATE capability_categories SET description =
    '规划项目目标、进度、预算、人员和风险，协调资源并保障项目交付的能力。'
WHERE code = 'C1.3';

UPDATE capability_categories SET description =
    '开展数学、物理、控制、机器人等基础理论及前沿方向探索、实验和学术研究的能力。'
WHERE code = 'C2.1';
UPDATE capability_categories SET description =
    '研究和设计机器学习、感知、规划、控制、强化学习及多模态智能算法的能力。'
WHERE code = 'C2.2';
UPDATE capability_categories SET description =
    '分析复杂系统需求，设计算法、数据、软件或机器人系统的总体架构和模块边界的能力。'
WHERE code = 'C2.3';

UPDATE capability_categories SET description =
    '使用编程语言、框架和工程方法开发、调试、维护软件及机器人应用的能力。'
WHERE code = 'C3.1';
UPDATE capability_categories SET description =
    '设计、开发和调试机械、电气、电子、嵌入式、传感器及计算硬件的能力。'
WHERE code = 'C3.2';
UPDATE capability_categories SET description =
    '完成软硬件集成、接口联调、环境部署、数据运维、可靠运行和故障处理的能力。'
WHERE code = 'C3.3';

UPDATE capability_categories SET description =
    '制定测试方案和质量标准，执行功能、性能、安全、可靠性及系统验证的能力。'
WHERE code = 'C4.1';
UPDATE capability_categories SET description =
    '设计和优化生产流程、制造工艺、装配方法、设备及量产导入过程的能力。'
WHERE code = 'C4.2';
UPDATE capability_categories SET description =
    '开展采购、供应商管理、物料计划、物流仓储、成本和供应质量管理的能力。'
WHERE code = 'C4.3';

UPDATE capability_categories SET description =
    '进行市场洞察、用户研究、品牌传播、内容运营和产品市场定位的能力。'
WHERE code = 'C5.1';
UPDATE capability_categories SET description =
    '识别客户需求、拓展业务机会、制定销售方案并维护客户关系的能力。'
WHERE code = 'C5.2';
UPDATE capability_categories SET description =
    '为产品部署、现场应用、故障诊断、客户培训和售后运营提供技术保障的能力。'
WHERE code = 'C5.3';

UPDATE capability_categories SET description =
    '开展招聘、绩效、薪酬、培训、组织发展和企业文化建设的能力。'
WHERE code = 'C6.1';
UPDATE capability_categories SET description =
    '开展财务分析、预算、税务、审计、合同、法务、风控和合规管理的能力。'
WHERE code = 'C6.2';
UPDATE capability_categories SET description =
    '提供行政、知识产权、标准、数据安全、信息化及其他专业职能支持的能力。'
WHERE code = 'C6.3';

INSERT INTO schema_migrations(version, description, source_sha256)
VALUES ('006', '能力方向与二级分类文字定义',
        'manual-006-capability-taxonomy-descriptions');
