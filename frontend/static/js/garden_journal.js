document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('journalEntryForm');
    if (!form) return;

    const entryIdInput = document.getElementById('entryIdInput');
    const journalIdInput = document.getElementById('journalIdInput');
    const plantSelect = document.getElementById('journalPlantSelect');
    const titleInput = document.getElementById('journalTitleInput');
    const dateInput = document.getElementById('journalDateInput');
    const heightInput = document.getElementById('journalHeightInput');
    const widthInput = document.getElementById('journalWidthInput');
    const notesInput = document.getElementById('journalNotesInput');
    const photoInput = document.getElementById('journalPhotoInput');
    const photoPreviewWrapper = document.getElementById('journalPhotoPreviewWrapper');
    const photoPreview = document.getElementById('journalPhotoPreview');
    const removePhotoGroup = document.getElementById('journalRemovePhotoGroup');
    const removePhotoCheckbox = document.getElementById('journalRemovePhoto');
    const startNewButtons = document.querySelectorAll('[data-action="start-new-journal"]');
    const logExistingButtons = document.querySelectorAll('[data-action="log-existing-journal"]');

    const defaultDate = form.dataset.today || '';
    const activePlantId = plantSelect ? plantSelect.dataset.activePlant || '' : '';
    const activeTitle = titleInput ? titleInput.dataset.activeTitle || '' : '';

    function setPlantRequired(required) {
        if (!plantSelect) return;
        if (required) {
            plantSelect.setAttribute('required', 'required');
        } else {
            plantSelect.removeAttribute('required');
        }
    }

    function togglePlantDisabled(disabled) {
        if (!plantSelect) return;
        plantSelect.disabled = disabled;
        plantSelect.classList.toggle('journal-input-disabled', disabled);
    }

    function toggleTitleReadonly(readonly) {
        if (!titleInput) return;
        titleInput.readOnly = readonly;
        titleInput.classList.toggle('journal-input-disabled', readonly);
    }

    function clearPhotoInput() {
        if (photoInput) {
            photoInput.value = '';
        }
        if (photoPreviewWrapper) {
            photoPreviewWrapper.classList.add('journal-hidden');
        }
        if (photoPreview) {
            photoPreview.src = '';
            photoPreview.removeAttribute('data-current-src');
        }
        if (removePhotoGroup) {
            removePhotoGroup.classList.add('journal-hidden');
        }
        if (removePhotoCheckbox) {
            removePhotoCheckbox.checked = false;
        }
    }

    function resetForm({ retainJournal } = { retainJournal: false }) {
        if (entryIdInput) {
            entryIdInput.value = '';
        }
        if (notesInput) {
            notesInput.value = '';
        }
        if (heightInput) {
            heightInput.value = '';
        }
        if (widthInput) {
            widthInput.value = '';
        }
        if (dateInput && defaultDate) {
            dateInput.value = defaultDate;
        }
        clearPhotoInput();

        if (retainJournal && journalIdInput && journalIdInput.value) {
            if (plantSelect) {
                plantSelect.value = activePlantId;
            }
            setPlantRequired(false);
            togglePlantDisabled(true);
            if (titleInput) {
                titleInput.value = activeTitle;
            }
            toggleTitleReadonly(true);
        } else {
            if (journalIdInput) {
                journalIdInput.value = '';
            }
            if (plantSelect) {
                plantSelect.value = '';
            }
            setPlantRequired(true);
            togglePlantDisabled(false);
            if (titleInput) {
                titleInput.value = '';
            }
            toggleTitleReadonly(false);
        }
    }

    function populateFormFromEntry(button) {
        if (!button) return;
        const entryId = button.dataset.entryId || '';
        const journalId = button.dataset.journalId || '';
        const plantId = button.dataset.plantId || '';
        const journalTitle = button.dataset.journalTitle || '';
        const entryDate = button.dataset.entryDate || defaultDate;
        const height = button.dataset.growthHeight || '';
        const width = button.dataset.growthWidth || '';
        const notes = button.dataset.notes || '';
        const photoUrl = button.dataset.photoUrl || '';

        if (entryIdInput) {
            entryIdInput.value = entryId;
        }
        if (journalIdInput) {
            journalIdInput.value = journalId;
        }
        if (plantSelect) {
            plantSelect.value = plantId || activePlantId;
        }
        if (titleInput) {
            titleInput.value = journalTitle || activeTitle;
        }
        if (dateInput) {
            dateInput.value = entryDate;
        }
        if (heightInput) {
            heightInput.value = height;
        }
        if (widthInput) {
            widthInput.value = width;
        }
        if (notesInput) {
            notesInput.value = notes;
        }

        setPlantRequired(false);
        togglePlantDisabled(true);
        toggleTitleReadonly(true);

        if (photoUrl && photoPreview && photoPreviewWrapper) {
            photoPreview.src = photoUrl;
            photoPreview.setAttribute('data-current-src', photoUrl);
            photoPreviewWrapper.classList.remove('journal-hidden');
            if (removePhotoGroup) {
                removePhotoGroup.classList.remove('journal-hidden');
            }
        } else {
            clearPhotoInput();
        }

        if (removePhotoCheckbox) {
            removePhotoCheckbox.checked = false;
        }

        const yOffset = form.getBoundingClientRect().top + window.scrollY - 120;
        window.scrollTo({ top: yOffset > 0 ? yOffset : 0, behavior: 'smooth' });
    }

    function handlePhotoPreview(file) {
        if (!file || !photoPreview || !photoPreviewWrapper) {
            clearPhotoInput();
            return;
        }
        const reader = new FileReader();
        reader.onload = event => {
            photoPreview.src = event.target?.result || '';
            if (photoPreview.src) {
                photoPreviewWrapper.classList.remove('journal-hidden');
            }
        };
        reader.readAsDataURL(file);
        if (removePhotoGroup) {
            removePhotoGroup.classList.remove('journal-hidden');
        }
        if (removePhotoCheckbox) {
            removePhotoCheckbox.checked = false;
        }
    }

    if (plantSelect && !journalIdInput.value) {
        setPlantRequired(true);
        togglePlantDisabled(false);
        toggleTitleReadonly(false);
    } else {
        setPlantRequired(false);
        togglePlantDisabled(true);
        toggleTitleReadonly(true);
        if (plantSelect) {
            plantSelect.value = activePlantId;
        }
        if (titleInput) {
            titleInput.value = activeTitle;
        }
    }

    if (dateInput && defaultDate && !dateInput.value) {
        dateInput.value = defaultDate;
    }

    document.querySelectorAll('.journal-entry-edit').forEach(button => {
        button.addEventListener('click', () => {
            populateFormFromEntry(button);
        });
    });

    startNewButtons.forEach(button => {
        button.addEventListener('click', () => {
            resetForm({ retainJournal: false });
        });
    });

    logExistingButtons.forEach(button => {
        button.addEventListener('click', () => {
            if (journalIdInput && journalIdInput.value) {
                resetForm({ retainJournal: true });
            } else {
                resetForm({ retainJournal: false });
            }
        });
    });

    if (removePhotoCheckbox && removePhotoGroup) {
        removePhotoCheckbox.addEventListener('change', () => {
            if (removePhotoCheckbox.checked) {
                if (photoPreviewWrapper) {
                    photoPreviewWrapper.classList.add('journal-hidden');
                }
            } else if (photoPreview && photoPreview.dataset.currentSrc) {
                photoPreviewWrapper.classList.remove('journal-hidden');
                photoPreview.src = photoPreview.dataset.currentSrc;
            }
        });
    }

    if (photoInput) {
        photoInput.addEventListener('change', event => {
            const file = event.target.files ? event.target.files[0] : null;
            handlePhotoPreview(file);
        });
    }
});
