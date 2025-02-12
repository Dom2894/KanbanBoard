// Variabile per tracciare l'elemento trascinato
let draggedItem = null;

// Funzione per consentire il trascinamento
function allowDrop(event) {
    event.preventDefault();
}

// Funzione per iniziare il trascinamento
function drag(event) {
    draggedItem = event.target;
    setTimeout(() => (draggedItem.style.opacity = '0.5'), 0);
}

// Funzione per rilasciare l'elemento
function drop(event) {
    event.preventDefault();
    const column = event.target.closest('.column');
    if (column && draggedItem.parentNode !== column) {
        column.querySelector('ul').appendChild(draggedItem);
        draggedItem.style.opacity = '1';
    }
}