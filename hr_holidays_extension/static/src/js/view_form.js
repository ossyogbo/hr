openerp.hr_holidays_extension = function (instance) {
    
    instance.web.form.FieldMany2One.include({
        events: {
            'change select': 'store_dom_value'
        },
        init: function(field_manager, node) {
            this._super(field_manager, node);
            this.refresh_field = this.node.attrs.refresh_field;
        },
        do_refresh_field: function() {
            if (this.refresh_field && this.get_value() != false) {
                var refresh_field = this.field_manager.fields[this.refresh_field];
                var value = refresh_field.get_value();
                delete refresh_field.display_value["" + value];
                refresh_field.reinit_value(value);
            }
        },
        render_value: function() {
            this._super();
            this.do_refresh_field();
        },
        store_dom_value: function () {
            this._super();
            this.do_refresh_field(); 
        }
    });
};
