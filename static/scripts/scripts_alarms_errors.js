document.addEventListener('DOMContentLoaded', () => {
    const pElements = document.querySelectorAll('.error-text');
    function highlightWords() {
        pElements.forEach(pElement =>{
            let htmlContent = pElement.innerHTML;
            const wordsToHighlight = [
                { word: 'Warning', className: 'highlight-yellow' },
                { word: 'Error', className: 'highlight-yellow' },
                { word: 'Alarm', className: 'highlight-red' }
            ];

            wordsToHighlight.forEach(item => {
                const regex = new RegExp(item.word, 'gi');
                htmlContent = htmlContent.replace(regex, match => {
                    return `<span class="${item.className}"><b>${match}</b></span>`;
                });
            });

            pElement.innerHTML = htmlContent;
        })
    }



    const dismissAll = document.getElementById('dismiss-all-form');
    dismissAll.addEventListener('submit', function(event){
        const confirmed = confirm('Dismiss ALL errors?');
            if(confirmed == true){
                this.submit();
            }
            else{
                event.preventDefault();
            }
    })

    highlightWords();
});