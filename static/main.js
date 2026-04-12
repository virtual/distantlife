(()=>{var e,r={151:(e,r,t)=>{t(305);window.onload=function(){n();var e=document.getElementById("menubutton"),r=document.getElementById("siteMenu");e.addEventListener("click",(function(t){"false"===r.getAttribute("aria-hidden")?(r.setAttribute("aria-hidden","true"),e.setAttribute("aria-expanded","false")):(r.setAttribute("aria-hidden","false"),e.setAttribute("aria-expanded","true"))}))};function n(){window.innerWidth<992?(menubutton.setAttribute("aria-expanded","false"),siteMenu.setAttribute("aria-hidden","true")):(menubutton.setAttribute("aria-expanded","true"),siteMenu.setAttribute("aria-hidden","false"))}window.onresize=n},753:()=>{},5:()=>{},683:()=>{},295:()=>{},988:()=>{},305:function(e){e.exports=function(){"use strict";var e={required:"This field is required",email:"This field requires a valid e-mail address",number:"This field requires a number",integer:"This field requires an integer value",url:"This field requires a valid website URL",tel:"This field requires a valid telephone number",maxlength:"This fields length must be < ${1}",minlength:"This fields length must be > ${1}",min:"Minimum value for this field is ${1}",max:"Maximum value for this field is ${1}",pattern:"Please match the requested format"};function r(e,r){for(;(e=e.parentElement)&&!e.classList.contains(r););return e}function t(e){var r=arguments;return this.replace(/\${([^{}]*)}/g,(function(e,t){return r[t]}))}function n(e){return e.pristine.self.form.querySelectorAll('input[name="'+e.getAttribute("name")+'"]:checked').length}function i(e,r){for(var t in r)t in e||(e[t]=r[t]);return e}function s(e){return!!(e&&e.constructor&&e.call&&e.apply)}var a={classTo:"form-group",errorClass:"has-danger",successClass:"has-success",errorTextParent:"form-group",errorTextTag:"div",errorTextClass:"text-help"},o="pristine-error",u="input:not([type^=hidden]):not([type^=submit]), select, textarea",l=["required","min","max","minlength","maxlength","pattern"],f=/^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/,c={},d=function(r,t){t.name=r,t.msg||(t.msg=e[r]),void 0===t.priority&&(t.priority=1),c[r]=t};function p(e,n,f){var d=this;function p(e,r,t){e.setAttribute("novalidate","true"),d.form=e,d.config=i(r||{},a),d.live=!(!1===t),d.fields=Array.from(e.querySelectorAll(u)).map(function(e){var r=[],t={},n={};return[].forEach.call(e.attributes,(function(e){if(/^data-pristine-/.test(e.name)){var i=e.name.substr(14);if(i.endsWith("-message"))return void(n[i.slice(0,i.length-8)]=e.value);"type"===i&&(i=e.value),m(r,t,i,e.value)}else~l.indexOf(e.name)?m(r,t,e.name,e.value):"type"===e.name&&m(r,t,e.value)})),r.sort((function(e,r){return r.priority-e.priority})),d.live&&e.addEventListener(~["radio","checkbox"].indexOf(e.getAttribute("type"))?"change":"input",function(e){d.validate(e.target)}.bind(d)),e.pristine={input:e,validators:r,params:t,messages:n,self:d}}.bind(d))}function m(e,r,t,n){var i=c[t];if(i&&(e.push(i),n)){var s=n.split(",");s.unshift(null),r[t]=s}}function h(e){for(var r=[],n=!0,i=0;e.validators[i];i++){var a=e.validators[i],o=e.params[a.name]?e.params[a.name]:[];if(o[0]=e.input.value,!a.fn.apply(e.input,o)){if(n=!1,s(a.msg))r.push(a.msg(e.input.value,o));else{var u=e.messages[a.name]||a.msg;r.push(t.apply(u,o))}if(!0===a.halt)break}}return e.errors=r,n}function v(e){if(e.errorElements)return e.errorElements;var t=r(e.input,d.config.classTo),n=null,i=null;return(n=d.config.classTo===d.config.errorTextParent?t:t.querySelector("."+d.config.errorTextParent))&&((i=n.querySelector("."+o))||((i=document.createElement(d.config.errorTextTag)).className=o+" "+d.config.errorTextClass,n.appendChild(i),i.pristineDisplay=i.style.display)),e.errorElements=[t,i]}function g(e){var r=v(e),t=r[0],n=r[1];t&&(t.classList.remove(d.config.successClass),t.classList.add(d.config.errorClass)),n&&(n.innerHTML=e.errors.join("<br/>"),n.style.display=n.pristineDisplay||"")}function y(e){var r=v(e),t=r[0],n=r[1];return t&&(t.classList.remove(d.config.errorClass),t.classList.remove(d.config.successClass)),n&&(n.innerHTML="",n.style.display="none"),r}function b(e){var r=y(e)[0];r&&r.classList.add(d.config.successClass)}return p(e,n,f),d.validate=function(e,r){r=e&&!0===r||!0===e;var t=d.fields;!0!==e&&!1!==e&&(e instanceof HTMLElement?t=[e.pristine]:(e instanceof NodeList||e instanceof(window.$||Array)||e instanceof Array)&&(t=Array.from(e).map((function(e){return e.pristine}))));for(var n=!0,i=0;t[i];i++){var s=t[i];h(s)?!r&&b(s):(n=!1,!r&&g(s))}return n},d.getErrors=function(e){if(!e){for(var r=[],t=0;t<d.fields.length;t++){var n=d.fields[t];n.errors.length&&r.push({input:n.input,errors:n.errors})}return r}return e.tagName&&"select"===e.tagName.toLowerCase()?e.pristine.errors:e.length?e[0].pristine.errors:e.pristine.errors},d.addValidator=function(e,r,t,n,i){e instanceof HTMLElement?(e.pristine.validators.push({fn:r,msg:t,priority:n,halt:i}),e.pristine.validators.sort((function(e,r){return r.priority-e.priority}))):console.warn("The parameter elem must be a dom element")},d.addError=function(e,r){(e=e.length?e[0]:e).pristine.errors.push(r),g(e.pristine)},d.reset=function(){for(var e=0;d.fields[e];e++)d.fields[e].errorElements=null;Array.from(d.form.querySelectorAll("."+o)).map((function(e){e.parentNode.removeChild(e)})),Array.from(d.form.querySelectorAll("."+d.config.classTo)).map((function(e){e.classList.remove(d.config.successClass),e.classList.remove(d.config.errorClass)}))},d.destroy=function(){d.reset(),d.fields.forEach((function(e){delete e.input.pristine})),d.fields=[]},d.setGlobalConfig=function(e){a=e},d}return d("text",{fn:function(e){return!0},priority:0}),d("required",{fn:function(e){return"radio"===this.type||"checkbox"===this.type?n(this):void 0!==e&&""!==e},priority:99,halt:!0}),d("email",{fn:function(e){return!e||f.test(e)}}),d("number",{fn:function(e){return!e||!isNaN(parseFloat(e))},priority:2}),d("integer",{fn:function(e){return!e||/^\d+$/.test(e)}}),d("minlength",{fn:function(e,r){return!e||e.length>=parseInt(r)}}),d("maxlength",{fn:function(e,r){return!e||e.length<=parseInt(r)}}),d("min",{fn:function(e,r){return!e||("checkbox"===this.type?n(this)>=parseInt(r):parseFloat(e)>=parseFloat(r))}}),d("max",{fn:function(e,r){return!e||("checkbox"===this.type?n(this)<=parseInt(r):parseFloat(e)<=parseFloat(r))}}),d("pattern",{fn:function(e,r){var t=r.match(new RegExp("^/(.*?)/([gimy]*)$"));return!e||new RegExp(t[1],t[2]).test(e)}}),p.addValidator=function(e,r,t,n,i){d(e,{fn:r,msg:t,priority:n,halt:i})},p}()}},t={};function n(e){var i=t[e];if(void 0!==i)return i.exports;var s=t[e]={exports:{}};return r[e].call(s.exports,s,s.exports,n),s.exports}n.m=r,e=[],n.O=(r,t,i,s)=>{if(!t){var a=1/0;for(f=0;f<e.length;f++){for(var[t,i,s]=e[f],o=!0,u=0;u<t.length;u++)(!1&s||a>=s)&&Object.keys(n.O).every((e=>n.O[e](t[u])))?t.splice(u--,1):(o=!1,s<a&&(a=s));if(o){e.splice(f--,1);var l=i();void 0!==l&&(r=l)}}return r}s=s||0;for(var f=e.length;f>0&&e[f-1][2]>s;f--)e[f]=e[f-1];e[f]=[t,i,s]},n.o=(e,r)=>Object.prototype.hasOwnProperty.call(e,r),(()=>{var e={522:0,158:0,830:0,281:0,10:0,870:0};n.O.j=r=>0===e[r];var r=(r,t)=>{var i,s,[a,o,u]=t,l=0;if(a.some((r=>0!==e[r]))){for(i in o)n.o(o,i)&&(n.m[i]=o[i]);if(u)var f=u(n)}for(r&&r(t);l<a.length;l++)s=a[l],n.o(e,s)&&e[s]&&e[s][0](),e[a[l]]=0;return n.O(f)},t=self.webpackChunk=self.webpackChunk||[];t.forEach(r.bind(null,0)),t.push=r.bind(null,t.push.bind(t))})(),n.O(void 0,[158,830,281,10,870],(()=>n(151))),n.O(void 0,[158,830,281,10,870],(()=>n(753))),n.O(void 0,[158,830,281,10,870],(()=>n(5))),n.O(void 0,[158,830,281,10,870],(()=>n(683))),n.O(void 0,[158,830,281,10,870],(()=>n(295)));var i=n.O(void 0,[158,830,281,10,870],(()=>n(988)));i=n.O(i)})();
document.addEventListener("DOMContentLoaded", function () {
	var buttons = document.querySelectorAll("[data-toggle-password]");

	buttons.forEach(function (button) {
		var inputId = button.getAttribute("data-toggle-password");
		var input = document.getElementById(inputId);
		var icon = button.querySelector("span.far, span.fas, span.fa");
		var srText = button.querySelector(".sr-only");
		var showText = button.getAttribute("data-show-label") || "Show password";
		var hideText = button.getAttribute("data-hide-label") || "Hide password";

		if (!input || !icon || !srText) {
			return;
		}

		button.addEventListener("click", function () {
			var showPassword = input.type === "password";
			input.type = showPassword ? "text" : "password";
			button.setAttribute("aria-pressed", String(showPassword));

			if (showPassword) {
				button.setAttribute("aria-label", hideText);
				srText.textContent = hideText;
				icon.classList.remove("fa-eye");
				icon.classList.add("fa-eye-slash");
			} else {
				button.setAttribute("aria-label", showText);
				srText.textContent = showText;
				icon.classList.remove("fa-eye-slash");
				icon.classList.add("fa-eye");
			}
		});
	});

	var signupForm = document.querySelector("[data-signup-password-form]");
	if (signupForm) {
		var passwordInput = signupForm.querySelector("#password");
		var confirmationInput = signupForm.querySelector("#confirmation");
		var submitButton = signupForm.querySelector('button[type="submit"], input[type="submit"]');
		var criteria = {
			length: signupForm.querySelector('[data-password-rule="length"]'),
			uppercase: signupForm.querySelector('[data-password-rule="uppercase"]'),
			lowercase: signupForm.querySelector('[data-password-rule="lowercase"]'),
			number: signupForm.querySelector('[data-password-rule="number"]'),
			symbol: signupForm.querySelector('[data-password-rule="symbol"]')
		};
		var passwordStartMessage = signupForm.getAttribute("data-password-start-message") || "Start typing a password to check it.";
		var passwordValidMessage = signupForm.getAttribute("data-password-valid-message") || "Password meets the requirements.";
		var passwordInvalidMessage = signupForm.getAttribute("data-password-invalid-message") || "Password does not meet the requirements.";
		var passwordMatchPrompt = signupForm.getAttribute("data-password-match-prompt") || "Retype your password to confirm it matches.";
		var passwordMatchValid = signupForm.getAttribute("data-password-match-valid") || "Passwords match.";
		var passwordMatchInvalid = signupForm.getAttribute("data-password-match-invalid") || "Passwords do not match.";
		var stateSuccess = signupForm.getAttribute("data-password-state-success") || "success";
		var stateError = signupForm.getAttribute("data-password-state-error") || "error";
		var stateNeutral = signupForm.getAttribute("data-password-state-neutral") || "status";
		var criteriaStatus = signupForm.querySelector("#password-criteria-status");
		var matchStatus = signupForm.querySelector("#password-match-status");
		var rules = Object.keys(criteria);

		if (passwordInput && confirmationInput && submitButton) {
			var setStatusState = function (element, state, message) {
				if (!element) {
					return;
				}
				var icon = element.querySelector(".status-icon");
				var stateLabel = element.querySelector(".status-state");
				var messageLabel = element.querySelector(".status-message");
				var isSuccess = state === "success";
				var isError = state === "error";

				if (icon) {
					icon.classList.remove("fa-check-circle", "fa-times-circle", "text-success", "text-danger", "d-none");
					if (isSuccess) {
						icon.classList.add("fa-check-circle", "text-success");
					} else if (isError) {
						icon.classList.add("fa-times-circle", "text-danger");
					} else {
						icon.classList.add("d-none");
					}
				}

				if (stateLabel) {
					stateLabel.textContent = state === "success" ? stateSuccess : state === "error" ? stateError : stateNeutral;
				}

				if (messageLabel && typeof message === "string") {
					messageLabel.textContent = message;
				}
			};

			var evaluatePassword = function () {
				var password = passwordInput.value || "";
				var checks = {
					length: password.length >= 12,
					uppercase: /[A-Z]/.test(password),
					lowercase: /[a-z]/.test(password),
					number: /\d/.test(password),
					symbol: /[^A-Za-z0-9]/.test(password)
				};
				var meetsCriteria = true;

				rules.forEach(function (rule) {
					var isValid = Boolean(checks[rule]);
					meetsCriteria = meetsCriteria && isValid;
				});

				var matches = password.length > 0 && password === confirmationInput.value;
				var confirmationFilled = confirmationInput.value.length > 0;
				var criteriaMessage = passwordStartMessage;
				var criteriaState = "neutral";

				if (password.length > 0) {
					if (meetsCriteria) {
						criteriaMessage = passwordValidMessage;
						criteriaState = "success";
					} else {
						criteriaMessage = passwordInvalidMessage;
						criteriaState = "error";
					}
				}

				if (criteriaStatus) {
					setStatusState(criteriaStatus, criteriaState, criteriaMessage);
				}

				if (matchStatus) {
					if (!confirmationFilled) {
						setStatusState(matchStatus, "neutral", passwordMatchPrompt);
					} else if (matches) {
						setStatusState(matchStatus, "success", passwordMatchValid);
					} else {
						setStatusState(matchStatus, "error", passwordMatchInvalid);
					}
				}

				passwordInput.setCustomValidity(password.length === 0 || meetsCriteria ? "" : passwordInvalidMessage);
				confirmationInput.setCustomValidity(confirmationFilled && !matches ? passwordMatchInvalid : "");
				submitButton.disabled = !(meetsCriteria && matches);
			};

			passwordInput.addEventListener("input", evaluatePassword);
			confirmationInput.addEventListener("input", evaluatePassword);
			evaluatePassword();
		}
	}
});

//# sourceMappingURL=main.js.map