/* static/admin/js/group_perm_admin.js */
'use strict';
{
    const $ = django.jQuery;

    // 使用更可靠的方式等待 DOM 和 jQuery 都准备好
    function initGroupPermAdmin() {
        // =======================================================
        // 1. 检查必要的元素是否存在
        // =======================================================
        const $ctSelect = $('#id_content_type');
        const $groupSelect = $('#id_group');
        const $objSelect = $('#id_object_selection');

        // 如果关键元素不存在，说明不在正确的页面上，直接返回
        if ($ctSelect.length === 0) {
            console.log("GroupObjectPermission form not found, skipping initialization.");
            return;
        }

        // =======================================================
        // 2. 初始化 Select2 配置
        // =======================================================
        const select2Config = { width: '100%' };

        // 应用 Select2 到下拉框（如果还没有初始化）
        if (!$ctSelect.hasClass('select2-hidden-accessible')) {
            $ctSelect.select2(select2Config);
        }
        if ($groupSelect.length > 0 && !$groupSelect.hasClass('select2-hidden-accessible')) {
            $groupSelect.select2(select2Config);
        }
        if ($objSelect.length > 0 && !$objSelect.hasClass('select2-hidden-accessible')) {
            $objSelect.select2({
                width: '100%',
                placeholder: '请先选择内容类型',
                allowClear: true
            });
        }

        // =======================================================
        // 3. 寻找权限复选框的容器
        // =======================================================
        let $permContainer = null;
        
        // 方法1: 尝试通过字段 ID 查找
        const $permField = $('#id_permissions');
        if ($permField.length > 0) {
            // 查找父容器，但排除 form 标签
            $permContainer = $permField.parent();
            if ($permContainer.is('form')) {
                $permContainer = null;
            } else {
                // 继续向上查找，找到合适的容器
                while ($permContainer.length > 0 && ($permContainer.is('form') || $permContainer.is('body'))) {
                    $permContainer = $permContainer.parent();
                }
            }
        }

        // 方法2: 通过 fieldset 或 field 类查找
        if (!$permContainer || $permContainer.length === 0) {
            // 查找包含 permissions 字段的 fieldset
            $permContainer = $('.field-permissions, .field-permissions_0, [class*="permissions"]')
                .find('div.related-widget-wrapper, div.help, ul, div').first();
        }

        // 方法3: 通过字段名查找父级 div
        if (!$permContainer || $permContainer.length === 0) {
            $permContainer = $permField.closest('div.field-permissions, div.form-row, div.form-group, div');
            if ($permContainer.length > 0 && !$permContainer.is('form')) {
                // 找到包含复选框的 div
                const $checkboxContainer = $permContainer.find('ul, div').first();
                if ($checkboxContainer.length > 0) {
                    $permContainer = $checkboxContainer;
                }
            }
        }

        // 方法4: 如果还是找不到，创建一个新的容器
        if (!$permContainer || $permContainer.length === 0) {
            // 在 permissions 字段后面创建一个容器
            if ($permField.length > 0) {
                $permContainer = $('<div id="permission-checkbox-container"></div>');
                $permField.after($permContainer);
            } else {
                // 如果连字段都找不到，尝试在 content_type 后面创建
                $permContainer = $('<div id="permission-checkbox-container" style="margin-top: 10px;"></div>');
                $ctSelect.closest('div').after($permContainer);
            }
        }

        // 给容器加个 ID 方便调试和后续操作
        if ($permContainer && $permContainer.length > 0) {
            $permContainer.attr('id', 'permission-checkbox-container');
            // 清除可能存在的默认文本（如 "None"）
            const containerText = $permContainer.text().trim();
            if (containerText === '-' || containerText === 'None' || containerText === '') {
                $permContainer.empty();
            }
        } else {
            console.error("Critical Error: Cannot find or create permission container in DOM.");
            return;
        }

        // =======================================================
        // 4. 获取后端注入的 AJAX URL
        // =======================================================
        let ajaxUrl = null;
        
        // 尝试多种方式获取 URL
        if ($ctSelect.length > 0) {
            ajaxUrl = $ctSelect.attr('data-ajax-url') || 
                     $ctSelect.data('ajax-url') || 
                     $ctSelect.data('ajaxUrl');
            
            // 如果还是获取不到，检查所有属性
            if (!ajaxUrl && $ctSelect[0]) {
                const attrs = Array.from($ctSelect[0].attributes);
                for (let attr of attrs) {
                    if (attr.name.includes('ajax') || attr.name.includes('url')) {
                        ajaxUrl = attr.value;
                        break;
                    }
                }
            }
        }
        
        // 调试信息
        if (!ajaxUrl) {
            console.warn("AJAX URL not found in data-ajax-url attribute. Trying to construct from form action...");
            // 尝试从表单 action 构建 URL
            const $form = $ctSelect.closest('form');
            if ($form.length > 0) {
                const formAction = $form.attr('action') || window.location.pathname;
                // 构建相对 URL
                ajaxUrl = formAction.replace(/\/add\/?$/, '/get-content-type-data/')
                                   .replace(/\/change\/\d+\/?$/, '/get-content-type-data/');
            }
        }
        
        if (ajaxUrl) {
            console.log("AJAX URL found:", ajaxUrl);
        } else {
            console.error("AJAX URL not found. Please check forms.py 'data-ajax-url' attribute.");
            $permContainer.html('<p style="color:red; padding:10px;">配置错误：无法获取接口地址。请检查表单配置。</p>');
            return;
        }

        // =======================================================
        // 5. 核心功能：加载数据 (对象列表 + 权限列表)
        // =======================================================
        const finalAjaxUrl = ajaxUrl; // 保存到闭包中
        const finalPermContainer = $permContainer; // 保存到闭包中
        
        function loadContextData(ctId, keepSelection) {
            /**
             * @param {string} ctId - ContentType 的 ID
             * @param {boolean} keepSelection - 是否保留当前选中的值（用于表单错误回填时的场景）
             */

            // 如果没有 ID，清空并退出
            if (!ctId) {
                if ($objSelect.length > 0) {
                    $objSelect.empty().trigger('change');
                }
                finalPermContainer.html('<p style="color:#999; padding:5px;">请先选择内容类型</p>');
                return;
            }

            // 如果不是"回填模式"，则显示加载状态
            if (!keepSelection) {
                if ($objSelect.length > 0) {
                    $objSelect.empty(); // 清空对象下拉框
                    // 必须手动触发 change 让 Select2 更新 UI (虽然此时是空的)
                    $objSelect.trigger('change');
                }

                // 显示加载提示
                finalPermContainer.html('<div style="padding:10px; color:#666;">正在加载数据...</div>');
            }

            // 使用保存的 URL
            const url = finalAjaxUrl;
            if (!url) {
                console.error("AJAX URL not found. Please check forms.py 'data-ajax-url' attribute.");
                finalPermContainer.html('<p style="color:red">配置错误：无法获取接口地址</p>');
                return;
            }

            // 发起 AJAX 请求
            $.ajax({
                url: url,
                data: {'ct_id': ctId},
                dataType: 'json',
                success: function(data) {
                    if (data.error) {
                        alert('后端错误: ' + data.error);
                        finalPermContainer.html('<p style="color:red">数据加载失败: ' + data.error + '</p>');
                        return;
                    }

                    // --- A. 填充对象下拉框 (Object Selection) ---
                    // 只有在非回填模式下才重绘对象列表，避免覆盖用户已选的值
                    if (!keepSelection && $objSelect.length > 0) {
                        $objSelect.empty();
                        // 添加空占位符
                        $objSelect.append(new Option('---------', '', true, true));

                        if (data.objects && data.objects.length > 0) {
                            data.objects.forEach(function(item) {
                                // new Option(text, value, defaultSelected, selected)
                                const option = new Option(item.text, item.id, false, false);
                                $objSelect.append(option);
                            });
                        } else {
                            $objSelect.append(new Option('（该类型下无可用对象）', '', false, false));
                        }
                        // 通知 Select2 更新
                        $objSelect.trigger('change');
                    }

                    // --- B. 填充权限多选框 (Permissions) ---
                    // 构建 HTML 字符串
                    let html = '<div id="id_permissions_wrapper" style="margin-top:5px;">';

                    if (data.permissions && data.permissions.length > 0) {
                        // 1. 添加"全选/反选"按钮
                        html += `
                            <div style="margin-bottom:10px; padding-bottom:5px; border-bottom:1px solid #eee;">
                                <button type="button" id="btn-toggle-all" class="button" style="cursor:pointer; padding:3px 8px;">全选/反选</button>
                            </div>
                            <div style="max-height: 300px; overflow-y: auto;">
                        `;

                        // 2. 循环添加 Checkbox
                        data.permissions.forEach(function(perm) {
                            // 注意：这里默认都不选中。如果需要回显，逻辑会更复杂，
                            // 通常依靠 Django 后端渲染回显，或者在此处对比 data.selected_ids
                            html += `
                                <div style="margin-bottom: 8px; display: flex; align-items: center;">
                                    <input type="checkbox" name="permissions" value="${perm.id}" id="perm_${perm.id}" style="margin-right: 8px;">
                                    <label for="perm_${perm.id}" style="margin:0; cursor:pointer; font-weight:normal; display:inline;">
                                        <span style="font-weight:bold;">${perm.name}</span> 
                                        <span style="color:#888; font-size:12px; margin-left:5px;">(${perm.codename})</span>
                                    </label>
                                </div>
                            `;
                        });
                        html += '</div>'; // 关闭滚动 div
                    } else {
                        html += '<p style="color:#999;">该内容类型未定义任何权限。</p>';
                    }
                    html += '</div>'; // 关闭 wrapper

                    // 渲染到页面
                    finalPermContainer.html(html);

                    // --- C. 绑定"全选"按钮事件 ---
                    // 先解绑避免重复绑定
                    $('#btn-toggle-all').off('click').on('click', function(e) {
                        e.preventDefault(); // 防止提交表单
                        const checkboxes = finalPermContainer.find('input[type="checkbox"]');
                        // 逻辑：只要有一个没选中，就执行"全选"；否则（即全都选中了）执行"全不选"
                        const notChecked = checkboxes.not(':checked');
                        if (notChecked.length > 0) {
                            checkboxes.prop('checked', true);
                        } else {
                            checkboxes.prop('checked', false);
                        }
                    });
                },
                error: function(xhr, status, error) {
                    console.error("AJAX Error:", status, error, xhr);
                    finalPermContainer.html('<p style="color:red">无法连接服务器，请检查网络。状态: ' + status + '</p>');
                }
            });
        }

        // =======================================================
        // 6. 事件监听与初始化
        // =======================================================

        // 监听 ContentType 变化
        $ctSelect.on('select2:select change', function(e) {
            // 当用户手动改变 ContentType 时，重新加载数据（不保留选中状态）
            loadContextData($(this).val(), false);
        });

        // 表单提交前验证
        const $form = $ctSelect.closest('form');
        if ($form.length > 0) {
            $form.on('submit', function(e) {
                // 验证对象选择
                const selectedObject = $objSelect.val();
                if (!selectedObject || selectedObject === '' || selectedObject === '---------') {
                    e.preventDefault();
                    alert('请选择目标对象。');
                    $objSelect.focus();
                    return false;
                }

                // 验证权限选择
                const checkedPerms = finalPermContainer.find('input[type="checkbox"]:checked');
                if (checkedPerms.length === 0) {
                    e.preventDefault();
                    alert('请至少选择一个权限。');
                    finalPermContainer.find('input[type="checkbox"]').first().focus();
                    return false;
                }

                return true;
            });
        }

        // 【页面加载时的初始化逻辑】
        // 场景：表单提交失败后（例如必填项漏填），Django 会重载页面并回填 ContentType。
        // 此时我们需要检查是否需要加载权限列表。
        const initialCtId = $ctSelect.val();

        // 检查页面上是否已经存在 Checkbox（如果是 Django 后端渲染的回显，可能已经存在了）
        const hasRenderedPerms = finalPermContainer.find('input[type="checkbox"]').length > 0;

        if (initialCtId && !hasRenderedPerms) {
            // 如果有 ContentType 但没有权限列表，说明是 JS 需要初始化的场景
            // 这里的 false 表示不保留对象选择（因为如果是全新的加载，对象下拉框需要根据 CT 重新拉取）
            // *注*：如果你希望在报错回显时保留"对象ID"，需要在 admin.py 的 Form __init__ 里处理 choices，
            // JS 这里主要负责渲染"权限列表"。
            loadContextData(initialCtId, false);
        }
    }

    // 等待 DOM 完全加载
    if (typeof django !== 'undefined' && django.jQuery) {
        $(document).ready(function() {
            // 延迟一点执行，确保所有 Django admin 脚本都已加载
            setTimeout(initGroupPermAdmin, 100);
        });
    } else {
        // 如果 django.jQuery 还没准备好，等待一下
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(initGroupPermAdmin, 200);
            });
        } else {
            setTimeout(initGroupPermAdmin, 100);
        }
    }
}
