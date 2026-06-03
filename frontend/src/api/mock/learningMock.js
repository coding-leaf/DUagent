export default function learningMock(mock) {
  // 生成资源库海量数据
  const generateResources = () => {
    const categories = ['基础结构', '排序算法', '图论专题', '动态规划', '高级树结构'];
    const types = ['Required', 'Recommended', 'Optional'];
    const icons = ['menu_book', 'play_circle', 'terminal', 'schema', 'quiz', 'build'];
    const resources = [];

    for (let i = 1; i <= 50; i++) {
      const type = types[i % 3];
      const category = categories[i % 5];
      
      let res = {
        id: `res_${i}`,
        title: `[${category}] 深度进阶与实践案例 - 第 ${i} 讲`,
        description: `全面剖析${category}的核心设计原则，对比不同算法在此场景下的性能极限，包含工业级代码实现与性能对比。`,
        category: category,
        type: type,
        badge: i % 4 === 0 ? '高阶难点' : null,
      };

      if (i % 5 === 0) {
        // Video style
        res.image = 'https://lh3.googleusercontent.com/aida-public/AB6AXuD29ZtHTVdxLScCBHl-JmHbt_8BnRdOmwjyIALZeNDFmW-L23xifi_lxqPsCTkiAId0WMVVS09tJjozfujiBjgfBdFfxj6AfO4mX78RAhwEGXjTjKTKwt_yAZOpfi5YhE9dJztsT1_RBqKjjnbqUjKA_mPxcAJH9JkYukBIjhpR_ZzAiRZOwXhc6_ytNoAes7yU8TMj2YnUGa7D8IdkGMN9-Gz3qedIYUHg01IhkFk_lxZ799E88He_ETD-N9wbzc2itxGS3b6IIi4R';
        res.duration = `${10 + (i % 20)} 课时`;
        res.tags = ['VIDEO', 'HIGH_QUALITY'];
      } else if (i % 5 === 1) {
        // Book/PDF style
        res.bookCard = true;
        res.image = 'https://lh3.googleusercontent.com/aida-public/AB6AXuBmA5my9dtHq2gVWsh2OaI2fpDx9DNVg95brXi1o36lMCDVrfTyELChL2xSYkANPJmxlpclUTteWc6m2YNqucbMTdSW6mRVa6jyyRiOnEKu1rj7Z1MuXF2mwIsYMIMp5E5NWdF_C-cmpPQkJgH2rY4XKiyaGpcFb8BUZLCWCn2vAXBlZcdSPjQ0P4dGc1xIACKDMRKjUWkXr4xIr_O1kxwiRaQ0tB0EeaJLtolJX4RxKMvJVyLN4uFTpk2WFOKYanT47PBNkvaIk5qO';
        res.author = 'DS 智能导师';
      } else if (i % 5 === 2) {
        // Code card style
        res.codeCard = true;
        res.fileName = `algo_practice_${i}.cpp`;
        res.icon = 'terminal';
        res.iconColor = 'text-cyan-400';
        res.iconBg = 'bg-cyan-400/20';
      } else {
        // Generic icon card
        res.icon = icons[i % icons.length];
        res.iconColor = ['text-purple-600', 'text-orange-500', 'text-cyan-600', 'text-emerald-500'][i % 4];
        res.iconBg = ['bg-purple-50', 'bg-orange-50', 'bg-cyan-50', 'bg-emerald-50'][i % 4];
        res.subText = i % 2 === 0 ? '核心知识点' : '练习与测验';
        if (i % 3 === 0) res.downloadable = true;
      }

      resources.push(res);
    }
    return resources;
  };

  const allResources = generateResources();

  // GET /api/v1/resources (支持分页)
  mock.onGet('/resources').reply((config) => {
    const page = config.params?.page || 1;
    const limit = config.params?.limit || 20;
    const start = (page - 1) * limit;
    const end = start + limit;
    const paginated = allResources.slice(start, end);

    return [200, {
      code: 200,
      message: 'success',
      data: {
        resources: paginated,
        total: allResources.length,
        page: page,
        page_size: limit
      }
    }];
  });

  // 复杂知识树
  mock.onGet('/learning-path').reply((config) => {
    return [200, {
      code: 200,
      message: 'success',
      data: {
        course_id: config.params?.course_id || 'course_1',
        nodes: [
          // 基础层
          { id: 'node_1', name: '数据结构概论', status: 'completed', mastery: 100, order: 1 },
          { id: 'node_2', name: '数组与字符串', status: 'completed', mastery: 95, order: 2 },
          { id: 'node_3', name: '链表基础', status: 'completed', mastery: 90, order: 3 },
          
          // 分支1: 栈与队列
          { id: 'node_4', name: '栈的实现与应用', status: 'in_progress', mastery: 65, order: 4 },
          { id: 'node_5', name: '队列与双端队列', status: 'pending', mastery: 0, order: 5 },
          
          // 分支2: 树
          { id: 'node_6', name: '二叉树遍历', status: 'completed', mastery: 85, order: 4 },
          { id: 'node_7', name: '二叉搜索树(BST)', status: 'in_progress', mastery: 40, order: 5 },
          { id: 'node_8', name: '平衡二叉树(AVL)', status: 'pending', mastery: 0, order: 6 },
          { id: 'node_9', name: '红黑树变色与旋转', status: 'pending', mastery: 0, order: 7 },
          { id: 'node_10', name: 'B树与B+树', status: 'pending', mastery: 0, order: 8 },

          // 分支3: 哈希
          { id: 'node_11', name: '哈希函数与冲突', status: 'pending', mastery: 0, order: 5 },

          // 综合层
          { id: 'node_12', name: '图论基础', status: 'pending', mastery: 0, order: 9 },
          { id: 'node_13', name: '最短路径算法', status: 'pending', mastery: 0, order: 10 }
        ],
        edges: [
          { from: 'node_1', to: 'node_2' },
          { from: 'node_2', to: 'node_3' },
          
          // 分支 1
          { from: 'node_3', to: 'node_4' },
          { from: 'node_4', to: 'node_5' },

          // 分支 2
          { from: 'node_3', to: 'node_6' },
          { from: 'node_6', to: 'node_7' },
          { from: 'node_7', to: 'node_8' },
          { from: 'node_8', to: 'node_9' },
          { from: 'node_7', to: 'node_10' },

          // 分支 3
          { from: 'node_2', to: 'node_11' },

          // 汇聚
          { from: 'node_5', to: 'node_12' },
          { from: 'node_9', to: 'node_12' },
          { from: 'node_10', to: 'node_12' },
          { from: 'node_11', to: 'node_12' },

          { from: 'node_12', to: 'node_13' }
        ],
        current_position: {
          node_id: 'node_4',
          node_name: '栈的实现与应用'
        }
      }
    }];
  });
}
