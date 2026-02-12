const url = window.location.href;
const service = document.querySelectorAll('.serv');
const details = document.getElementsByClassName('details');
const csrf = document.getElementsByName('csrfmiddlewaretoken')[0].value;
const resultsBox = document.getElementById('results-box');
const resultsBoxMobile = document.getElementById('results-box-mobile');
const accounts = document.getElementById('accounts');
const accdetail = document.getElementById('accdetail');
const accdetailMobile = document.getElementById('accdetail-mobile');
const mainAccdetail = document.getElementById('main-accdetail');
const duration = document.getElementById('duration');
const end = document.getElementById('end');
const ticket = document.getElementById('comp');
const modalContent = document.getElementById('modal-body');
const modalTitle = document.getElementById('modal-title');
const closeModal = document.getElementById('close');
const modal = document.getElementById('modal');
const inputListAcc = document.getElementById('bank');
const dataListAcc = document.getElementById('banklist');
const modalButtons = document.getElementById('modal-footer');
const paymentMethod = document.getElementById('method');
const listPaymentMethod = document.getElementById('paymentlist');
const changeService = document.getElementById('service');

// Variables para búsqueda (global para acceso desde template)
window.allAccounts = [];
let allAccounts = window.allAccounts;

const isMobileView = () => window.matchMedia('(max-width: 767.98px)').matches;

function toggleResultCardSelection(event, checkboxId) {
  const checkbox = document.getElementById(checkboxId);
  if (!checkbox) return;

  const interactiveTarget = event.target.closest(
    'button, a, textarea, select, option, label'
  );

  if (interactiveTarget) return;

  if (event.target === checkbox) {
    detail();
    return;
  }

  checkbox.checked = !checkbox.checked;
  detail();
}

window.toggleResultCardSelection = toggleResultCardSelection;

const renderNoResults = () => {
  if (resultsBox) {
    resultsBox.innerHTML =
      '<tr><td colspan="6" class="text-center"><b>No se encontraron resultados</b></td></tr>';
  }
  if (resultsBoxMobile) {
    resultsBoxMobile.innerHTML =
      '<div class="mobile-result-card"><b>No se encontraron resultados</b></div>';
  }
};

const renderSalesSearchResults = (accountsData) => {
  if (!Array.isArray(accountsData) || accountsData.length === 0) {
    renderNoResults();
    return;
  }

  if (resultsBox) {
    resultsBox.innerHTML = '';
  }
  if (resultsBoxMobile) {
    resultsBoxMobile.innerHTML = '';
  }

  if (isMobileView() && resultsBoxMobile) {
    accountsData.forEach((data, index) => {
      const cardClass = index === 0 ? 'mobile-result-card selected' : 'mobile-result-card';
      const checkboxId = `serv-mobile-${data.id}-${index}`;
      resultsBoxMobile.innerHTML += `
        <div class="${cardClass} mobile-result-card-selectable"
             role="button"
             tabindex="0"
             onclick="toggleResultCardSelection(event, '${checkboxId}')"
             onkeydown="if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggleResultCardSelection(event, '${checkboxId}'); }">
          <div class="d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-2">
              <img src="${data.logo}" width="24" style="object-fit: contain;" alt="logo">
              <strong>${data.email}</strong>
            </div>
            <input class="form-check-input details"
                   name="serv"
                   id="${checkboxId}"
                   type="checkbox"
                   value="${data.id}"
                   onclick="event.stopPropagation(); detail()">
          </div>
          <div class="mobile-result-grid">
            <div><small>Clave</small><code>${data.password}</code></div>
            <div><small>Perfil</small><span>${data.profile}</span></div>
            <div><small>Vencimiento Cta</small><span>${moment(data.expiration_acc).format(
              'DD/MM/YYYY'
            )}</span></div>
            <div><small>ID Cuenta</small><span>${data.id}</span></div>
          </div>
        </div>
      `;
    });
    return;
  }

  if (resultsBox) {
    accountsData.forEach((data, index) => {
      const borderStyle = index === 0 ? 'border: 2px solid green;' : '';
      const checkboxId = `serv-desktop-${data.id}-${index}`;
      resultsBox.innerHTML += `
        <tr style="${borderStyle}">
          <td><input class="form-check-input details" name="serv" id="${checkboxId}" type="checkbox" value="${
            data.id
          }" onclick="detail()"></td>
          <td><img src="${data.logo}" width="20" style="object-fit: contain;" alt="logo"></td>
          <td>${data.email}</td>
          <td>${data.password}</td>
          <td>${moment(data.expiration_acc).format('DD/MM/YYYY')}</td>
          <td>${data.profile}</td>
        </tr>
      `;
    });
  }
};

window.renderSalesSearchResults = renderSalesSearchResults;

const renderSalesDetailResults = (detailsData) => {
  if (accdetail) {
    accdetail.innerHTML = '';
  }
  if (accdetailMobile) {
    accdetailMobile.innerHTML = '';
  }

  detailsData.forEach((data, index) => {
    const statusText = data.status ? 'Suspender' : 'Reactivar';
    const buttonClass = data.status ? 'btn-danger' : 'btn-success';

    if (isMobileView() && accdetailMobile) {
      accdetailMobile.innerHTML += `
        <div class="mobile-result-card ${index === 0 ? 'selected' : ''}">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <div class="d-flex align-items-center gap-2">
              <img src="${data.logo}" width="24" style="object-fit: contain;" alt="logo">
              <strong>${data.email}</strong>
            </div>
            <button class="btn btn-sm ${buttonClass}" onclick="toggleAccountStatus(${data.id}, '${
        data.email
      }')" title="${statusText}">
              ${statusText}
            </button>
          </div>
          <div class="mobile-result-grid">
            <div><small>Cliente</small><span>${NotNull(data.customer)}</span></div>
            <div><small>Vencimiento Cliente</small><span>${data.customer_end_date}</span></div>
            <div><small>Perfil</small><span>${data.profile}</span></div>
            <div><small>ID Cuenta</small><span>${data.id}</span></div>
          </div>
        </div>
      `;
      return;
    }

    if (accdetail) {
      accdetail.innerHTML += `
        <tr>
          <td><img src="${data.logo}" width="20" style="object-fit: contain;" alt="logo"></td>
          <td>${data.email}</td>
          <td>${NotNull(data.customer)}</td>
          <td>${data.customer_end_date}</td>
          <td>${data.profile}</td>
          <td>
            <button class="btn btn-sm ${buttonClass}" onclick="toggleAccountStatus(${data.id}, '${
        data.email
      }')" title="${statusText}">
              ${statusText}
            </button>
          </td>
        </tr>
      `;
    }
  });
};

const filterResults = (searchTerm) => {
  console.log('filterResults called with:', searchTerm);
  console.log('allAccounts length:', allAccounts.length);

  const filteredAccounts = allAccounts.filter((account) => {
    const matches = account.email.toLowerCase().includes(searchTerm.toLowerCase());
    console.log(`Checking ${account.email}: ${matches}`);
    return matches;
  });

  console.log('Filtered results:', filteredAccounts.length);
  renderSalesSearchResults(filteredAccounts);
};

// Event delegation - configurar una sola vez cuando el documento esté listo
$(document).ready(function () {
  console.log('Document ready, setting up search listener');

  // Usar event delegation para que funcione incluso si el elemento se carga después
  $(document).on('input', '#search-email', function (e) {
    const searchTerm = $(this).val();
    console.log('🔍 Search term:', searchTerm);
    console.log('📊 Total accounts:', allAccounts.length);
    filterResults(searchTerm);
  });

  console.log('✅ Search listener configured');
});

const sendSearchData = (data) => {
  try {
    $.ajax({
      type: 'POST',
      url: '/adm/sales/search',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
      data: {
        csrfmiddlewaretoken: csrf,
        'data[]': data,
        page: 1,
      },
      success: (res) => {
        console.log('Response:', res);
        const responseData = res.data;

        if (Array.isArray(responseData)) {
          allAccounts = responseData;
          window.allAccounts = responseData;
          console.log('Total accounts loaded:', allAccounts.length);
          renderSalesSearchResults(responseData);

          console.log('✅ Accounts loaded and ready for search');
          console.log('📧 First account email:', responseData[0]?.email);
        } else {
          if (resultsBox) {
            resultsBox.innerHTML = `<tr><td colspan="6"><b>${responseData}</b></td></tr>`;
          }
          if (resultsBoxMobile) {
            resultsBoxMobile.innerHTML = `<div class="mobile-result-card"><b>${responseData}</b></div>`;
          }
          allAccounts = [];
          accounts.classList.add('not-visible');
        }
      },
      error: (error) => {
        console.error('Error:', error);
      },
    });
  } catch (error) {
    console.error(error);
  }
};

const sendSearchDetailData = (det) => {
  $.ajax({
    type: 'POST',
    url: '/adm/sales/search/detail',
    data: {
      csrfmiddlewaretoken: csrf,
      'det[]': det,
    },
    success: (det) => {
      const data = det.det;

      if (Array.isArray(data)) {
        renderSalesDetailResults(data);
      } else {
        if (accdetail) {
          accdetail.innerHTML = `<b>${data}</b>`;
        }
        if (accdetailMobile) {
          accdetailMobile.innerHTML = `<div class="mobile-result-card"><b>${data}</b></div>`;
        }
        mainAccdetail.classList.add('not-visible');
      }
    },
  });
};

function convertDateFormat(string) {
  if (string === 'Disponible') {
    return 'Disponible';
  } else {
    moment(string).format('DD/MM/YYYY');
  }
}

function NotNull(string) {
  if (string == null) {
    return 'Disponible';
  } else {
    return string;
  }
}

function detail() {
  var det = [];
  Array.prototype.filter.call(details, (e) => {
    if (e.checked == true) {
      det.push(e.value);
    }
  });
  mainAccdetail.classList.remove('not-visible');
  sendSearchDetailData(det);
}

function services() {
  var arr = [];
  service.forEach((e) => {
    if (e.checked == true) {
      console.log(e.value);
      console.log(duration.value);
      arr.push(
        JSON.stringify({
          service: e.value,
          duration: duration.value,
        })
      );
    }
  });
  if (arr.length > 0 && duration.value != 'None' && duration.value != '') {
    accounts.classList.remove('not-visible');
    sendSearchData(arr);
  } else if (accounts) {
    accounts.classList.add('not-visible');
  }
  CheckFields();
}

function CheckFields() {
  const selectedServices = Array.from(service).filter((e) => e.checked).length;
  const validDuration = duration.value != 'None' && duration.value != '';

  if (selectedServices > 0 && validDuration) {
    end.disabled = false;
  } else {
    end.disabled = true;
  }
}

function changeTicket() {
  $('#modal').modal('hide');
  ticket.value = '';
}

function changeAcc() {
  inputListAcc.value = '';
  $('#modal').modal('hide');
}

function changeMethod() {
  paymentMethod.value = '';
  $('#modal').modal('hide');
}

ticket.addEventListener('change', () => {
  $.ajax({
    type: 'POST',
    url: '/adm/sales/check/ticket',
    data: {
      csrfmiddlewaretoken: csrf,
      data: ticket.value,
    },
    success: (data) => {
      const res = data.data;
      if (Array.isArray(res)) {
        modalTitle.innerHTML = `El comprobante ${res[0].ticket} ya fue utilizado`;
        modalContent.innerHTML = '';
        res.forEach((res) => {
          modalContent.innerHTML += `
              <p>
              <b>E-Mail: </b> ${res.email} - <b>Cliente: </b> ${res.customer} - <b>Fecha: </b> ${res.date}
              </p>
            `;
          modalButtons.innerHTML = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Utilizar de todas formas</button>
            <button class="btn btn-primary" onclick="changeTicket()">Cambiar Comprobante</button>
            `;
        });
        $('#modal').modal('show');
      }
    },
  });
});

duration.addEventListener('change', () => {
  services();
});

inputListAcc.addEventListener('change', () => {
  if (inputListAcc.value.length > 0) {
    var counter = 0;
    var exist = false;
    try {
      while (counter <= dataListAcc.options.length) {
        if (inputListAcc.value == dataListAcc.options[counter].value) {
          exist = true;
          break;
        } else {
          counter += 1;
        }
      }
      if (exist === false) {
        modalTitle.innerHTML = `Error`;
        modalContent.innerHTML = 'La cuenta ingresada no existe, porfavor verificar';
        modalButtons.innerHTML = '';
        modalButtons.innerHTML =
          '<button class="btn btn-primary" onclick="changeAcc()">Corregir Número de cuenta</button>';
        $('#modal').modal('show');
      }
    } catch {
      modalTitle.innerHTML = `Error`;
      modalContent.innerHTML = 'La cuenta ingresada no existe, porfavor verificar';
      modalButtons.innerHTML = '';
      modalButtons.innerHTML =
        '<button class="btn btn-primary" onclick="changeAcc()">Corregir Número de cuenta</button>';
      $('#modal').modal('show');
    }
  }
});

paymentMethod.addEventListener('change', () => {
  if (paymentMethod.value.length > 0) {
    var counter = 0;
    var exist = false;
    try {
      while (counter <= listPaymentMethod.options.length) {
        if (paymentMethod.value == listPaymentMethod.options[counter].value) {
          exist = true;
          break;
        } else {
          counter += 1;
        }
      }
      if (exist === false) {
        modalTitle.innerHTML = `Error`;
        modalContent.innerHTML = 'El metodo de pago no existe';
        modalButtons.innerHTML = '';
        modalButtons.innerHTML =
          '<button class="btn btn-primary" onclick="changeMethod()">Corregir metodo de pago</button>';
        $('#modal').modal('show');
      }
    } catch {
      modalTitle.innerHTML = `Error`;
      modalContent.innerHTML = 'El metodo de pago no existe';
      modalButtons.innerHTML = '';
      modalButtons.innerHTML =
        '<button class="btn btn-primary" onclick="changeMethod()">Corregir metodo de pago</button>';
      $('#modal').modal('show');
    }
  }
});
// Función para suspender/reactivar una cuenta
function toggleAccountStatus(accountId, email) {
  if (confirm(`¿Deseas cambiar el estado de la cuenta ${email}?`)) {
    $.ajax({
      type: 'POST',
      url: '/adm/account/toggle-status',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/json',
      },
      data: JSON.stringify({
        account_id: accountId,
        csrfmiddlewaretoken: csrf,
      }),
      success: (response) => {
        if (response.success) {
          alert(response.message);
          // Recargar la tabla de detalles
          detail();
        } else {
          alert('Error: ' + response.message);
        }
      },
      error: (error) => {
        console.error('Error:', error);
        alert('Hubo un error al cambiar el estado de la cuenta');
      },
    });
  }
}
