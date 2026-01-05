/**
 * 作业模板Admin界面主要功能
 */
(function($) {
    'use strict';
    
    // 等待DOM加载完成
    $(document).ready(function() {
        initJobTemplateAdmin();
    });
    
    /**
     * 初始化作业模板Admin界面
     */
    function initJobTemplateAdmin() {
        // 初始化步骤管理
        initStepManagement();
        
        // 初始化模板验证
        initTemplateValidation();
        
        // 初始化批量操作
        initBulkOperations();
        
        // 初始化搜索和过滤
        initSearchAndFilter();
        
        // 初始化帮助提示
        initHelpTooltips();
    }
    
    /**
     * 初始化步骤管理功能
     */
    function initStepManagement() {
        // 自动设置步骤顺序
        autoSetStepOrder();
        
        // 步骤拖拽排序
        initStepDragAndDrop();
        
        // 步骤复制功能
        initStepCopy();
        
        // 步骤模板功能
        initStepTemplates();
    }
    
    /**
     * 自动设置步骤顺序
     */
    function autoSetStepOrder() {
        $('.inline-related').each(function(index) {
            var orderField = $(this).find('input[name*="order"]');
            if (orderField.length && !orderField.val()) {
                orderField.val(index + 1);
            }
        });
    }
    
    /**
     * 初始化步骤拖拽排序
     */
    function initStepDragAndDrop() {
        if (typeof $.fn.sortable !== 'undefined') {
            $('.inline-group').sortable({
                items: '.inline-related',
                handle: '.inline-related h3',
                axis: 'y',
                update: function(event, ui) {
                    updateStepOrder();
                }
            });
        }
    }
    
    /**
     * 更新步骤顺序
     */
    function updateStepOrder() {
        $('.inline-related').each(function(index) {
            var orderField = $(this).find('input[name*="order"]');
            if (orderField.length) {
                orderField.val(index + 1);
                // 更新顺序指示器
                var indicator = $(this).find('.step-order-indicator');
                if (indicator.length) {
                    indicator.text(index + 1);
                }
            }
        });
    }
    
    /**
     * 初始化步骤复制功能
     */
    function initStepCopy() {
        // 为每个步骤添加复制按钮
        $('.inline-related').each(function() {
            if (!$(this).find('.copy-step-btn').length) {
                var copyBtn = $('<button type="button" class="copy-step-btn" style="float: right; margin: 5px 10px; background: #ffc107; color: #212529; border: none; padding: 3px 8px; border-radius: 3px; font-size: 11px;">复制</button>');
                $(this).find('h3').append(copyBtn);
                
                copyBtn.on('click', function() {
                    copyStep($(this).closest('.inline-related'));
                });
            }
        });
    }
    
    /**
     * 复制步骤
     */
    function copyStep(stepElement) {
        var stepData = {};
        
        // 收集步骤数据
        stepElement.find('input, select, textarea').each(function() {
            var name = $(this).attr('name');
            if (name) {
                stepData[name] = $(this).val();
            }
        });
        
        // 点击添加按钮
        $('.add-row a').click();
        
        // 等待新步骤加载完成后填充数据
        setTimeout(function() {
            var newStep = $('.inline-related').last();
            newStep.find('input, select, textarea').each(function() {
                var name = $(this).attr('name');
                if (name && stepData[name]) {
                    $(this).val(stepData[name]);
                    // 触发change事件以更新字段显示
                    $(this).trigger('change');
                }
            });
            
            // 更新顺序
            updateStepOrder();
        }, 200);
    }
    
    /**
     * 初始化步骤模板功能
     */
    function initStepTemplates() {
        // 添加步骤模板选择器
        if (!$('.step-template-selector').length) {
            var templateSelector = $('<div class="step-template-selector" style="margin: 20px 0; padding: 15px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;"><h4 style="margin: 0 0 10px 0;">常用步骤模板</h4><div class="template-buttons"></div></div>');
            
            var templates = [
                { name: 'Shell脚本', type: 'script', script_type: 'shell' },
                { name: 'Python脚本', type: 'script', script_type: 'python' },
                { name: '文件上传', type: 'file_transfer' }
            ];
            
            templates.forEach(function(template) {
                var btn = $('<button type="button" class="template-btn" style="margin: 5px; padding: 8px 15px; background: #007bff; color: white; border: none; border-radius: 4px;">' + template.name + '</button>');
                templateSelector.find('.template-buttons').append(btn);
                
                btn.on('click', function() {
                    addStepFromTemplate(template);
                });
            });
            
            $('.inline-group').before(templateSelector);
        }
    }
    
    /**
     * 从模板添加步骤
     */
    function addStepFromTemplate(template) {
        // 点击添加按钮
        $('.add-row a').click();
        
        // 等待新步骤加载完成后填充模板数据
        setTimeout(function() {
            var newStep = $('.inline-related').last();
            
            // 设置步骤类型
            newStep.find('select[name*="step_type"]').val(template.type).trigger('change');
            
            // 设置其他字段
            if (template.script_type) {
                newStep.find('select[name*="script_type"]').val(template.script_type);
            }
            // transfer_type 已废弃
            
            // 更新顺序
            updateStepOrder();
        }, 200);
    }
    
    /**
     * 初始化模板验证
     */
    function initTemplateValidation() {
        // 表单提交前验证
        $('form').on('submit', function(e) {
            if (!validateJobTemplate()) {
                e.preventDefault();
                return false;
            }
        });
        
        // 实时验证
        $('input[name*="name"], input[name*="order"], input[name*="timeout"]').on('blur', function() {
            validateField($(this));
        });
    }
    
    /**
     * 验证作业模板
     */
    function validateJobTemplate() {
        var isValid = true;
        var errors = [];
        
        // 检查模板名称
        var templateName = $('input[name="name"]').val();
        if (!templateName || templateName.trim().length < 2) {
            errors.push('模板名称至少需要2个字符');
            isValid = false;
        }
        
        // 检查步骤数量
        var stepCount = $('.inline-related').length;
        if (stepCount === 0) {
            errors.push('至少需要添加一个作业步骤');
            isValid = false;
        }
        
        // 检查步骤顺序
        var orders = [];
        $('input[name*="order"]').each(function() {
            var order = parseInt($(this).val());
            if (order && orders.indexOf(order) !== -1) {
                errors.push('步骤顺序不能重复');
                isValid = false;
                return false;
            }
            if (order) orders.push(order);
        });
        
        // 显示错误信息
        if (!isValid) {
            showValidationErrors(errors);
        }
        
        return isValid;
    }
    
    /**
     * 验证单个字段
     */
    function validateField(field) {
        var name = field.attr('name');
        var value = field.val();
        
        // 移除之前的错误提示
        field.removeClass('error');
        field.next('.validation-error').remove();
        
        if (name.includes('order') || name.includes('timeout')) {
            var numValue = parseInt(value);
            if (isNaN(numValue) || numValue < 1) {
                field.addClass('error');
                var errorMsg = name.includes('order') ? '执行顺序必须大于0' : '超时时间必须大于0';
                field.after('<div class="validation-error" style="color: red; font-size: 12px;">' + errorMsg + '</div>');
            }
        }
    }
    
    /**
     * 显示验证错误
     */
    function showValidationErrors(errors) {
        // 移除之前的错误提示
        $('.validation-errors').remove();
        
        var errorHtml = '<div class="validation-errors" style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; padding: 15px; margin: 20px 0; color: #721c24;"><h4 style="margin: 0 0 10px 0;">请修正以下错误：</h4><ul style="margin: 0; padding-left: 20px;">';
        
        errors.forEach(function(error) {
            errorHtml += '<li>' + error + '</li>';
        });
        
        errorHtml += '</ul></div>';
        
        $('form').prepend(errorHtml);
        
        // 滚动到错误提示
        $('html, body').animate({
            scrollTop: $('.validation-errors').offset().top - 100
        }, 500);
    }
    
    /**
     * 初始化批量操作
     */
    function initBulkOperations() {
        // 添加批量操作按钮
        if (!$('.bulk-actions').length) {
            var bulkActions = $('<div class="bulk-actions" style="margin: 20px 0; padding: 15px; background: #e9ecef; border-radius: 5px;"><h4 style="margin: 0 0 10px 0;">批量操作</h4><div class="bulk-buttons"></div></div>');
            
            var actions = [
                { name: '批量设置超时', action: 'setTimeout' },
                { name: '批量设置忽略错误', action: 'setIgnoreError' },
                { name: '批量删除', action: 'delete' }
            ];
            
            actions.forEach(function(action) {
                var btn = $('<button type="button" class="bulk-btn" data-action="' + action.action + '" style="margin: 5px; padding: 8px 15px; background: #6c757d; color: white; border: none; border-radius: 4px;">' + action.name + '</button>');
                bulkActions.find('.bulk-buttons').append(btn);
                
                btn.on('click', function() {
                    executeBulkAction(action.action);
                });
            });
            
            $('.inline-group').before(bulkActions);
        }
    }
    
    /**
     * 执行批量操作
     */
    function executeBulkAction(action) {
        var selectedSteps = $('.inline-related input[type="checkbox"]:checked').closest('.inline-related');
        
        if (selectedSteps.length === 0) {
            alert('请先选择要操作的步骤');
            return;
        }
        
        switch (action) {
            case 'setTimeout':
                var timeout = prompt('请输入超时时间（秒）:', '300');
                if (timeout && !isNaN(timeout)) {
                    selectedSteps.find('input[name*="timeout"]').val(timeout);
                }
                break;
                
            case 'setIgnoreError':
                var ignoreError = confirm('是否设置所有选中步骤为忽略错误？');
                if (ignoreError) {
                    selectedSteps.find('input[name*="ignore_error"]').prop('checked', true);
                }
                break;
                
            case 'delete':
                if (confirm('确定要删除选中的步骤吗？')) {
                    selectedSteps.find('.inline-deletelink').click();
                }
                break;
        }
    }
    
    /**
     * 初始化搜索和过滤
     */
    function initSearchAndFilter() {
        // 添加步骤搜索框
        if (!$('.step-search').length) {
            var searchBox = $('<div class="step-search" style="margin: 20px 0;"><input type="text" placeholder="搜索步骤..." class="search-input" style="width: 100%; padding: 8px 12px; border: 1px solid #ced4da; border-radius: 4px; box-sizing: border-box;"></div>');
            
            $('.inline-group').before(searchBox);
            
            searchBox.find('.search-input').on('input', function() {
                var searchTerm = $(this).val().toLowerCase();
                filterSteps(searchTerm);
            });
        }
    }
    
    /**
     * 过滤步骤
     */
    function filterSteps(searchTerm) {
        $('.inline-related').each(function() {
            var stepText = $(this).text().toLowerCase();
            if (searchTerm === '' || stepText.includes(searchTerm)) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    }
    
    /**
     * 初始化帮助提示
     */
    function initHelpTooltips() {
        // 为重要字段添加帮助提示
        var helpFields = [
            { selector: 'input[name="name"]', help: '作业模板的名称，用于标识和管理' },
            { selector: 'select[name*="step_type"]', help: '选择步骤类型：脚本执行或文件传输' },
            { selector: 'input[name*="order"]', help: '步骤执行顺序，数字越小越先执行' },
            { selector: 'input[name*="timeout"]', help: '步骤超时时间（秒），超时后自动终止' },
            { selector: 'input[name*="ignore_error"]', help: '勾选后即使步骤失败也继续执行后续步骤' }
        ];
        
        helpFields.forEach(function(field) {
            var element = $(field.selector);
            if (element.length && !element.next('.help-tooltip').length) {
                var helpIcon = $('<span class="help-icon" style="margin-left: 5px; color: #007bff; cursor: help;" title="' + field.help + '">?</span>');
                element.after(helpIcon);
            }
        });
    }
    
})(django.jQuery);
