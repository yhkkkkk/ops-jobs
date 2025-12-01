/**
 * 作业步骤动态字段显示控制
 */
(function($) {
    'use strict';
    
    // 等待DOM加载完成
    $(document).ready(function() {
        initJobStepFields();
        
        // 监听动态添加的步骤
        $(document).on('change', 'select[name*="step_type"]', function() {
            toggleStepFields($(this));
        });
        
        // 监听添加新步骤按钮
        $(document).on('click', '.add-row a', function() {
            setTimeout(function() {
                initJobStepFields();
            }, 100);
        });
    });
    
    /**
     * 初始化作业步骤字段
     */
    function initJobStepFields() {
        $('select[name*="step_type"]').each(function() {
            toggleStepFields($(this));
        });
        
        // 添加步骤顺序指示器
        addStepOrderIndicators();
        
        // 添加步骤类型标签
        addStepTypeTags();
    }
    
    /**
     * 根据步骤类型切换字段显示
     */
    function toggleStepFields(selectElement) {
        var stepContainer = selectElement.closest('.inline-related');
        var stepType = selectElement.val();
        
        // 隐藏所有类型相关字段
        stepContainer.find('.step-script-fields, .step-transfer-fields').hide();
        
        // 根据类型显示相应字段
        if (stepType === 'script') {
            showScriptFields(stepContainer);
        } else if (stepType === 'file_transfer') {
            showTransferFields(stepContainer);
        }
        
        // 更新步骤类型标签
        updateStepTypeTag(stepContainer, stepType);
    }
    
    /**
     * 显示脚本相关字段
     */
    function showScriptFields(container) {
        var scriptFields = container.find('.field-script_type, .field-script_content');
        var transferFields = container.find('.field-transfer_type, .field-local_path, .field-remote_path');
        
        // 显示脚本字段
        scriptFields.show();
        scriptFields.closest('.form-row').addClass('step-script-fields');
        
        // 隐藏传输字段
        transferFields.hide();
        transferFields.closest('.form-row').removeClass('step-transfer-fields');
        
        // 添加脚本字段标题
        if (!container.find('.step-script-fields h4').length) {
            scriptFields.closest('.form-row').prepend('<h4>脚本配置</h4>');
        }
    }
    
    /**
     * 显示文件传输相关字段
     */
    function showTransferFields(container) {
        var scriptFields = container.find('.field-script_type, .field-script_content');
        var transferFields = container.find('.field-transfer_type, .field-local_path, .field-remote_path');
        
        // 隐藏脚本字段
        scriptFields.hide();
        scriptFields.closest('.form-row').removeClass('step-script-fields');
        
        // 显示传输字段
        transferFields.show();
        transferFields.closest('.form-row').addClass('step-transfer-fields');
        
        // 添加传输字段标题
        if (!container.find('.step-transfer-fields h4').length) {
            transferFields.closest('.form-row').prepend('<h4>文件传输配置</h4>');
        }
    }
    
    /**
     * 添加步骤顺序指示器
     */
    function addStepOrderIndicators() {
        $('.inline-related').each(function(index) {
            var orderField = $(this).find('input[name*="order"]');
            if (orderField.length && !$(this).find('.step-order-indicator').length) {
                var orderValue = orderField.val() || (index + 1);
                orderField.before('<span class="step-order-indicator">' + orderValue + '</span>');
            }
        });
    }
    
    /**
     * 添加步骤类型标签
     */
    function addStepTypeTags() {
        $('.inline-related').each(function() {
            var stepTypeSelect = $(this).find('select[name*="step_type"]');
            var stepType = stepTypeSelect.val();
            
            if (stepType && !$(this).find('.step-type-tag').length) {
                var tagText = stepType === 'script' ? '脚本' : '传输';
                var tagClass = stepType === 'script' ? 'script' : 'file_transfer';
                stepTypeSelect.after('<span class="step-type-tag ' + tagClass + '">' + tagText + '</span>');
            }
        });
    }
    
    /**
     * 更新步骤类型标签
     */
    function updateStepTypeTag(container, stepType) {
        var existingTag = container.find('.step-type-tag');
        if (existingTag.length) {
            existingTag.remove();
        }
        
        if (stepType) {
            var tagText = stepType === 'script' ? '脚本' : '传输';
            var tagClass = stepType === 'script' ? 'script' : 'file_transfer';
            container.find('select[name*="step_type"]').after('<span class="step-type-tag ' + tagClass + '">' + tagText + '</span>');
        }
    }
    
    /**
     * 优化表单布局
     */
    function optimizeFormLayout() {
        // 为必填字段添加标识
        $('label[for*="name"], label[for*="step_type"], label[for*="order"]').each(function() {
            if (!$(this).find('.required-indicator').length) {
                $(this).append('<span class="required-indicator" style="color: red;"> *</span>');
            }
        });
        
        // 优化字段宽度
        $('.field-box').each(function() {
            var fieldName = $(this).find('input, select, textarea').attr('name') || '';
            if (fieldName.includes('order') || fieldName.includes('timeout')) {
                $(this).css('width', '150px');
            } else if (fieldName.includes('ignore_error')) {
                $(this).css('width', '200px');
            }
        });
    }
    
    /**
     * 添加字段验证提示
     */
    function addFieldValidation() {
        $('input[name*="timeout"]').on('blur', function() {
            var value = parseInt($(this).val());
            if (value < 1) {
                $(this).addClass('error');
                if (!$(this).next('.validation-error').length) {
                    $(this).after('<div class="validation-error" style="color: red; font-size: 12px;">超时时间必须大于0</div>');
                }
            } else {
                $(this).removeClass('error');
                $(this).next('.validation-error').remove();
            }
        });
        
        $('input[name*="order"]').on('blur', function() {
            var value = parseInt($(this).val());
            if (value < 1) {
                $(this).addClass('error');
                if (!$(this).next('.validation-error').length) {
                    $(this).after('<div class="validation-error" style="color: red; font-size: 12px;">执行顺序必须大于0</div>');
                }
            } else {
                $(this).removeClass('error');
                $(this).next('.validation-error').remove();
            }
        });
    }
    
    // 延迟执行布局优化
    setTimeout(function() {
        optimizeFormLayout();
        addFieldValidation();
    }, 500);
    
})(django.jQuery);
