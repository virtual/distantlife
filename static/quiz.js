// quiz.js - page-specific quiz initialization
document.addEventListener('DOMContentLoaded', function () {
    try {
        var quizForms = document.querySelectorAll('.form-quiz-container');
        quizForms.forEach(function (form) {
            try {
                var ele = form.querySelectorAll('input[name="wordchoice"]');
                if (!ele || ele.length === 0) return;

                function handleSelection(e) {
                    for (var i = 0; i < ele.length; i++) {
                        if (ele[i].checked) {
                            var datatype = ele[i].dataset.type;
                            var label = document.querySelector('label[for="' + ele[i].id + '"]');
                            if (label) {
                                label.classList.add('btn-' + datatype);
                            }
                            if (datatype == 'success') {
                                var expEl = form.querySelector('#experience');
                                if (expEl) {
                                    expEl.value = String(parseInt(expEl.value || '0') + 1);
                                }
                            }
                        }
                        ele[i].disabled = true;
                    }
                    var skipBtn = form.querySelector('#buttonSkip');
                    var contBtn = form.querySelector('#buttonContinue');
                    if (skipBtn) skipBtn.style.display = 'none';
                    if (contBtn) contBtn.style.display = 'inline-block';
                }

                for (var i = 0; i < ele.length; i++) {
                    ele[i].addEventListener('change', handleSelection);
                }
            } catch (err) {
                console.error('Quiz init error', err);
            }
        });
    } catch (err) {
        console.error('Quiz module error', err);
    }
});
