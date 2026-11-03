'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let token = sessionStorage.getItem('rps_token');
let me, active = 'Overview', generation = 0;
const dirtyMarks = new Set();
async function discardUnsavedMarks(){if(dirtyMarks.size&&!await confirmAction('You have unsaved marks. Leave without saving?'))return false;dirtyMarks.clear();return true;}
window.addEventListener('beforeunload',event=>{if(dirtyMarks.size){event.preventDefault();event.returnValue='';}});
let lookups = {departments: [], sessions: []};
const definitions = {
 'Batch settings': {path:'/cohorts',key:'cohorts',fields:[['department_id','Department','departments'],['session_id','Session','sessions'],['current_semester','Current semester','number'],['processing_semester','Result processing semester','number'],['automatic_core','Fixed core enrollment','booleans']]},
 Departments: {path:'/departments', key:'departments', fields:[['name','Department name']]},
 Sessions: {path:'/sessions', key:'sessions', fields:[['name','Academic session']]},
 Students: {path:'/students', key:'students', fields:[['student_id','Student code'],['name','Full name'],['email','Email','email'],['department_id','Department','departments'],['session_id','Session','sessions']]},
 Teachers: {path:'/teachers', key:'teachers', fields:[['teacher_id','Teacher code'],['name','Full name'],['email','Email','email'],['department_id','Department','departments']]},
 Courses: {path:'/courses', key:'courses', fields:[['course_code','Course code'],['course_name','Course name'],['credit','Credits','number'],['semester','Semester','number'],['department_id','Department','departments'],['category','Course type','categories']]},
 Accounts: {path:'/accounts', key:'accounts', fields:[['username','Username'],['role','Role','roles'],['reference_id','Student / teacher code (blank for admin)']]}
};
async function api(path, options = {}) {
 const sentToken=token;
 const response = await fetch(path, {...options, headers:{...(options.body ? {'Content-Type':'application/json'} : {}), ...(token ? {Authorization:`Bearer ${token}`} : {}), ...options.headers}});
 let data;try{data=await response.json();}catch{throw new Error('The server could not complete this request. Please try again.');}
 if (!response.ok) {
  if (response.status === 401 && path !== '/login' && token===sentToken) logout(true);
  const detail = Array.isArray(data.detail) ? data.detail.map(x => `${x.loc.slice(1).join(' ')}: ${x.msg}`).join('; ') : data.detail;
  throw new Error(detail==='Not Found'?'The running server does not have this page. Restart the app server, then refresh.':detail || 'The request could not be completed.');
 }
 return data;
}
function notice(message='', success=false) { $('notice').textContent=message; $('notice').className=success?'success':''; }
async function logout(force=false) { if(!force&&!await discardUnsavedMarks())return;dirtyMarks.clear();token=null; me=null; sessionStorage.removeItem('rps_token'); generation++; $('editor').close();$('confirmation').close('cancel'); $('portal').hidden=true; $('loginView').hidden=false; $('loginForm').reset(); }
$('logoutButton').onclick=()=>logout();
$('loginForm').onsubmit=async event=>{
 event.preventDefault(); const button=event.submitter; button.disabled=true; $('loginMessage').textContent='';
 try {
  const form=new FormData(event.target); const response=await fetch('/login',{method:'POST',body:new URLSearchParams(form)}); const data=await response.json();
  if(!response.ok) throw new Error(data.detail || 'Sign in failed');
  token=data.access_token; sessionStorage.setItem('rps_token',token); event.target.reset(); await start();
 } catch(error) { $('loginMessage').textContent=error.message; } finally {button.disabled=false;}
};
function navigationIcon(name){
 const paths={
  'Overview':'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  'Teacher assignment':'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M16 10l2 2 4-4',
  'Batch settings':'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
  'Departments':'M3 21h18 M5 21V7l7-4 7 4v14 M9 10h1 M14 10h1 M9 14h1 M14 14h1 M10 21v-3h4v3',
  'Sessions':'M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2 M7 14h3 M14 14h3',
  'Students':'M2 8l10-5 10 5-10 5z M6 10v7c4 3 8 3 12 0v-7 M22 8v8',
  'Teachers':'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M20 21v-2a4 4 0 0 0-3-4 M16 3a4 4 0 0 1 0 8',
  'Courses':'M12 5C8 2 5 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-3-1-6-2-10 1z M12 5v16',
  'Accounts':'M9 14a6 6 0 1 1 4-4l8 8-3 3-3-3-2 2-3-3 M6 6h.01',
  'Publish results':'M8 3H4v18h16V7l-4-4H8 M9 12l2 2 5-5 M8 18h8',
  'Student results':'M4 3v18h17 M8 16v-5 M13 16V7 M18 16v-9',
  'My courses':'M12 5C8 2 5 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-3-1-6-2-10 1z M12 5v16',
  'My results':'M4 3v18h17 M8 16v-5 M13 16V7 M18 16v-9'
 };
 return `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]??paths.Overview}"/></svg>`;
}

async function start() {
 me=await api('/me'); $('loginView').hidden=true; $('portal').hidden=false;
 $('identity').innerHTML=`<span class="identity-avatar" aria-hidden="true">${esc(me.username.slice(0,1).toUpperCase())}</span><div><strong>${esc(me.username)}</strong><br><span class="badge">${esc(me.role)}</span></div>`;
 const pages=me.role==='admin'?['Overview','Teacher assignment',...Object.keys(definitions),'Publish results','Student results']:me.role==='teacher'?['My courses']:['My results'];
 $('navigation').innerHTML=pages.map(name=>`<button data-page="${esc(name)}">${navigationIcon(name)}<span>${esc(name)}</span></button>`).join('');
 $('navigation').querySelectorAll('button').forEach(b=>b.onclick=()=>show(b.dataset.page));
 if(me.must_change_password) { $('content').innerHTML='<div class="card"><h2>Choose your own password</h2><p class="help">Your temporary password must be changed before you can use the portal. Select Change password to continue.</p></div>'; $('pageTitle').textContent='Welcome'; changePassword(); return; }
 lookups=await api('/lookups'); await show(pages[0]);
}
$('refreshButton').onclick=()=>show(active);
$('closeDialog').onclick=()=>{if(!$('editForm').querySelector('[type=submit]').disabled)$('editor').close();};
$('editor').addEventListener('cancel',event=>{if($('editForm').querySelector('[type=submit]').disabled)event.preventDefault();});
function dialog(title, fields, save) {
 $('dialogTitle').textContent=title; $('fields').innerHTML=fields; $('formError').textContent=''; $('fields').oninput=null; $('editForm').querySelector('[type=submit]').textContent='Save';
 $('editForm').onsubmit=async event=>{
  event.preventDefault(); const button=event.submitter; button.disabled=true; $('formError').textContent='';
  try { const close=await save(new FormData(event.target)); if(close!==false)$('editor').close(); } catch(error) {$('formError').textContent=error.message;} finally {button.disabled=false;}
 }; $('editor').showModal();
}
function changePassword() {
 dialog('Change password','<label>Current password<input name="current_password" type="password" required autocomplete="current-password"></label><label>New password · 12–128 characters<input name="new_password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label><label>Confirm new password<input name="confirmation" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>',async form=>{
  if(form.get('new_password')!==form.get('confirmation'))throw new Error('New passwords do not match');
  await api('/change-password',{method:'POST',body:JSON.stringify({current_password:form.get('current_password'),new_password:form.get('new_password')})});
  await logout(true); $('loginMessage').textContent='Password changed. Sign in with your new password.';
 });
}
$('passwordButton').onclick=async()=>{if(await discardUnsavedMarks())changePassword();};
async function show(page) {
 if(!await discardUnsavedMarks())return;
 active=page; const current=++generation; notice(); $('pageTitle').textContent=page;
 $('navigation').querySelectorAll('button').forEach(b=>{const selected=b.dataset.page===page;b.classList.toggle('active',selected);if(selected)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
 $('content').innerHTML='<div class="card muted">Loading…</div>';
 try {
  if(me.must_change_password) {changePassword();return;}
  const freshLookups=await api('/lookups');if(current!==generation)return;lookups=freshLookups;
  if(page==='Teacher assignment'||page==='Semester planning') await semesterPlan(current);
  else if(page==='Batch settings') await batchSettings(current);
  else if(definitions[page]) await management(page,current);
  else if(page==='Overview') await overview(current);
  else if(page==='My courses') await teacherPage(current);
  else if(page==='Publish results') await publication(current);
  else await resultsPage(current);
 } catch(error) {if(current===generation){$('content').innerHTML='<div class="card">This page could not be loaded. Try Refresh.</div>';notice(error.message);}}
}
async function overview(current) {
 const names=['Students','Teachers','Courses','Enrollments'];
 const counts=await Promise.all(names.map(async name=>{const def=name==='Enrollments'?{path:'/course-students',key:'enrollments'}:definitions[name];return (await api(def.path))[def.key].length;}));
 if(current!==generation)return;
 const notes=['Registered students','Academic staff','Curriculum courses','Fixed course registrations'];
 $('content').innerHTML=`<section class="welcome-banner"><div><p class="eyebrow">YOUR DEPARTMENT AT A GLANCE</p><h2>A clear view of academic progress.</h2><p>Manage your courses, support your teachers, and keep results moving.</p></div><svg class="banner-emblem" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M8 24l24-12 24 12-24 12z M17 29v16c10 8 20 8 30 0V29 M56 24v19"/><circle cx="56" cy="47" r="3"/></svg></section><div class="stats dashboard-stats">${names.map((n,i)=>`<div class="card stat"><span class="muted">${n==='Enrollments'?'Registrations':n}</span><strong>${counts[i].toLocaleString()}</strong><span class="stat-note">${notes[i]}</span></div>`).join('')}</div><div class="dashboard-columns"><section class="card"><p class="eyebrow">FROM CLASSROOM TO RESULTS</p><h2>Keep things moving.</h2><ol class="workflow"><li><div><strong>Assign your teachers</strong>Choose the session, semester, and the right teacher for each course.</div></li><li><div><strong>Give everyone access</strong>Create teacher and student accounts from the Accounts page.</div></li><li><div><strong>Enter &amp; review marks</strong>Teachers save assessment marks. You review the complete breakdown.</div></li><li><div><strong>Publish with confidence</strong>Publish reviewed results so students can see their grades and CGPA.</div></li></ol></section><section class="card"><p class="eyebrow">ACADEMIC SESSIONS</p><h2>Batch progress</h2>${lookups.cohorts?.length?lookups.cohorts.map(c=>`<div class="batch-row"><h3>${esc(displayValue('department_id',c.department_id))} <span class="muted">/ ${esc(displayValue('session_id',c.session_id))}</span></h3><div class="semester-pair"><span>Currently studying<strong>Semester ${c.current_semester}</strong></span><span>Processing results<strong>Semester ${c.processing_semester}</strong></span></div><p class="muted small">${c.automatic_core?'Fixed courses are assigned automatically. Electives are selected separately.':'Course enrollments are managed by the administrator.'}</p></div>`).join(''):'<p class="help">Set up your first academic batch in Batch settings.</p>'}</section></div><details class="policy-details"><summary>Grading policy &amp; calculation rules</summary><p class="help">Assessments total 150: assignment 10, class test 20, midterm 40, final 80. Grades use the percentage of 150. A+ ≥80%, A ≥75%, A− ≥70%, B+ ≥65%, B ≥60%, B− ≥55%, C+ ≥50%, C ≥45%, D ≥40%, otherwise F.</p><p class="help">GPA and CGPA are weighted by credits. Failed published courses count with zero grade points; pending courses are excluded. Each course has one enrollment per student. Retakes are not supported. Confirm the grading policy with your institution before using real results.</p></details>`;

}
function table(headers, rows) {return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.join(''):`<tr><td colspan="${headers.length}" class="empty">No records yet.</td></tr>`}</tbody></table></div>`;}
function credentials(data) {
 $('content').prepend(Object.assign(document.createElement('div'),{className:'card credentials',textContent:`Account credentials — copy and share securely now.\nUsername: ${data.username}\nTemporary password: ${data.temporary_password}\nThe user must change this password on first sign-in.`}));
}
async function management(page,current) {
 const def=definitions[page]; const rows=(await api(def.path))[def.key];
 if(current!==generation)return;
 const keys=rows.length?Object.keys(rows[0]).filter(k=>k!=='id'):def.fields.map(f=>f[0]);
 $('content').innerHTML=`<div class="toolbar"><input id="search" type="search" placeholder="Search ${page.toLowerCase()}…" aria-label="Search records">${['Students','Teachers'].includes(page)?'<button id="bulkImport">Import CSV</button>':''}<button id="addRecord" class="primary">+ Add ${page.toLowerCase()}</button></div>`+table([...keys.map(k=>k.replaceAll('_',' ')),'Actions'],rows.map(row=>`<tr>${keys.map(k=>`<td>${esc(displayValue(k,row[k]))}</td>`).join('')}<td>${page==='Accounts'?`<button data-reset="${row.id}">Reset password</button>`:!['Assignments','Enrollments'].includes(page)?`<button data-edit="${row.id}">Edit</button>`:''}<button data-delete="${row.id}" class="danger">Delete</button></td></tr>`));
 $('search').oninput=event=>document.querySelectorAll('#content tbody tr').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(event.target.value.toLowerCase()));
 $('addRecord').onclick=()=>editRecord(page);
 if($('bulkImport'))$('bulkImport').onclick=()=>bulkImport(page);
 document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editRecord(page,rows.find(r=>r.id===Number(b.dataset.edit))));
 document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=async()=>{
  if(!await confirmAction('Delete this record? This cannot be undone.'))return;
  b.disabled=true; try {await api(`${def.path}/${b.dataset.delete}`,{method:'DELETE'});lookups=await api('/lookups');await show(page);notice('Record deleted.',true);} catch(e){notice(e.message);b.disabled=false;}
 });
 document.querySelectorAll('[data-reset]').forEach(b=>b.onclick=async()=>{
  if(!await confirmAction('Replace this user’s password and sign them out?'))return;
  b.disabled=true;try{credentials(await api(`/accounts/${b.dataset.reset}/reset-password`,{method:'POST'}));}catch(e){notice(e.message);}finally{b.disabled=false;}
 });
}
function displayValue(key,value) {
 if(key==='department_id')return lookups.departments.find(x=>x.id===value)?.name??value;
 if(key==='session_id')return lookups.sessions.find(x=>x.id===value)?.name??value;
 return value===true?'Yes':value===false?'No':value;
}
async function editRecord(page,row) {
 if(page==='Accounts'&&!row){await createAccountDialog();return;}
 try {
  const def=definitions[page]; const sources={...lookups,booleans:[{value:'true',label:'Automatic'},{value:'false',label:'Manual'}],categories:[{value:'core',label:'Core'},{value:'optional theory',label:'Optional theory'},{value:'optional lab',label:'Optional lab'}],roles:[{value:'student',label:'Student'},{value:'teacher',label:'Teacher'},{value:'admin',label:'Admin'}]};
  for(const source of new Set(def.fields.map(f=>f[2]).filter(x=>['students','teachers','courses'].includes(x)))) sources[source]=(await api('/'+source))[source];
  const fields=def.fields.map(([key,label,type])=>{
   const value=row?.[key]??'';let input;
   if(sources[type]) {
    input=`<select name="${key}" required><option value="">Select ${esc(label.toLowerCase())}</option>${sources[type].map(x=>{const code=x.value??(['departments','sessions'].includes(type)?x.id:type==='courses'?x.course_code:type==='teachers'?x.teacher_id:x.student_id);return `<option value="${esc(code)}" ${String(code)===String(value)?'selected':''}>${esc(x.label??(x.course_code?`${x.course_code} · ${x.course_name}`:x.teacher_id?`${x.teacher_id} · ${x.name}`:x.student_id?`${x.student_id} · ${x.name}`:x.name))}</option>`;}).join('')}</select>`;
   } else input=`<input name="${key}" type="${type??'text'}" value="${esc(value)}" ${key==='reference_id'?'':'required'} ${['student_id','teacher_id','course_code','username','reference_id'].includes(key)?'maxlength="30" pattern="[A-Za-z0-9_-]+"':type==='email'?'maxlength="254"':page==='Sessions'?'maxlength="50"':'maxlength="100"'} ${row&&['student_id','teacher_id','course_code'].includes(key)?'readonly':''} ${type==='number'?`min="${key==='credit'?'0.01':'1'}" max="${key==='credit'?'10':'8'}" step="${key==='credit'?'0.01':'1'}"`:''}>`;
   return `<label>${esc(label)}${input}</label>`;
  }).join('');
  dialog(`${row?'Edit':'Add'} ${page.toLowerCase()}`,fields,async form=>{
   const data=Object.fromEntries(form);
   for(const key of ['department_id','session_id','credit','semester'])if(key in data)data[key]=Number(data[key]);
   if(page==='Accounts'&&!data.reference_id)data.reference_id=null;
   for(const key of ['current_semester','processing_semester'])if(key in data)data[key]=Number(data[key]);
   if('automatic_core' in data)data.automatic_core=data.automatic_core==='true';
   const result=await api(def.path+(row?`/${row.id}`:''),{method:row?'PUT':'POST',body:JSON.stringify(data)});
   lookups=await api('/lookups'); await show(page); if(result.temporary_password)credentials(result);else notice('Record saved.',true);
  });
 } catch(e){notice(e.message);}
}
async function teacherPage(current) {
 const courses=(await api(`/teacher-courses/${encodeURIComponent(me.reference_id)}`)).courses;
 if(current!==generation)return;
 $('content').innerHTML=`<div class="card"><h2>Your assigned courses</h2><p class="muted">Save each student’s marks. An administrator reviews and publishes results.</p><label>Course<select id="courseChoice"><option value="">Select a course</option>${courses.map(c=>`<option value="${c.session_id}:${esc(c.course_code)}">${esc(c.session_name)} · Semester ${c.semester} · ${esc(c.course_code)} · ${esc(c.course_name)}</option>`).join('')}</select></label></div><div id="marksArea"></div>`;
 let marksRequest=0, previousChoice='';
 $('courseChoice').onchange=async event=>{
  if(!await discardUnsavedMarks()){event.target.value=previousChoice;return;}
  notice();
  previousChoice=event.target.value;
  const choice=event.target.value, request=++marksRequest; $('marksArea').innerHTML='';if(!choice)return;
  const [sessionId,code]=choice.split(':');
  try {
   const response=await api(`/teacher-courses/${encodeURIComponent(me.reference_id)}/${encodeURIComponent(code)}/marks?session_id=${sessionId}`);
   const students=response.students;
   const entryAllowed=response.entry_allowed!==false;
   if(current!==generation||request!==marksRequest)return;
   if(!entryAllowed)notice('This is a future semester. Marks entry opens when the admin updates the current semester.');
   const fields=['assignment_marks','class_test_marks','midterm_marks','final_marks'];const maxima=[10,20,40,80];
   $('marksArea').innerHTML=`<div class="toolbar"><input id="marksSearch" type="search" placeholder="Search student name or ID…" aria-label="Search students for marks"><p class="muted small">${students.length} students · Save each student separately</p></div><div class="course-cards">${students.map(s=>`<section class="card marks-card" data-student-marks="${esc(s.student_id)}" data-revision="${s.revision??''}"><span class="badge">${esc(s.student_id)}</span><h2>${esc(s.name)}</h2><div class="marks-fields">${fields.map((f,i)=>`<label>${['Assignment /10','Class test /20','Midterm /40','Final /80'][i]}<input type="number" required min="0" max="${maxima[i]}" step="0.01" data-field="${f}" aria-label="${esc(f.replaceAll('_',' '))} for ${esc(s.student_id)}" value="${esc(s[f]??'')}" ${s.published||!entryAllowed?'disabled':''}></label>`).join('')}</div><div class="marks-summary"><span>Total: <strong class="total">${esc(s.total_marks??'—')}</strong> /150</span><span>Grade: <strong class="grade">${esc(s.grade??'—')}</strong></span><span class="badge">${s.published?'Published':'Draft'}</span></div><button class="primary" data-save="${esc(s.student_id)}" ${s.published||!entryAllowed?'disabled':''}>${s.published?'Published · locked':!entryAllowed?'Future semester · locked':'Save marks'}</button></section>`).join('')||'<div class="card muted">No students are enrolled in this course.</div>'}</div>`;
   $('marksSearch').oninput=event=>{const query=event.target.value.toLowerCase();document.querySelectorAll('[data-student-marks]').forEach(card=>card.hidden=!card.textContent.toLowerCase().includes(query));};
   document.querySelectorAll('[data-save]').forEach(b=>b.onclick=async()=>{
    const row=b.closest('[data-student-marks]');const data={};if(row.dataset.revision)data.revision=Number(row.dataset.revision); for(const input of row.querySelectorAll('input')){if(!input.value.trim()||!input.checkValidity()){input.reportValidity();notice('Enter all four marks within their allowed limits.');return;}data[input.dataset.field]=Number(input.value);}
    const inputs=Array.from(row.querySelectorAll('input'));inputs.forEach(input=>input.disabled=true);b.disabled=true;
    try{
     const result=await api(`/teacher-courses/${encodeURIComponent(me.reference_id)}/${encodeURIComponent(code)}/marks/${encodeURIComponent(b.dataset.save)}?session_id=${sessionId}`,{method:'POST',body:JSON.stringify(data)});
     if(current!==generation||request!==marksRequest)return;
     row.querySelector('.total').textContent=result.marks.total_marks;row.querySelector('.grade').textContent=result.marks.grade;row.dataset.revision=result.marks.revision;dirtyMarks.delete(b.dataset.save);b.textContent='Saved';notice(`Marks saved for ${b.dataset.save}.`,true);
    }catch(e){if(current===generation&&request===marksRequest)notice(e.message);}finally{b.disabled=false;inputs.forEach(input=>input.disabled=false);}

   });
   document.querySelectorAll('[data-save]').forEach(button=>{button.closest('[data-student-marks]').querySelectorAll('input').forEach(input=>input.oninput=()=>{dirtyMarks.add(button.dataset.save);button.textContent='Save changes';});});
  }catch(e){notice(e.message);}
 };
 const preferred=courses.find(course=>lookups.cohorts?.some(c=>c.department_id===course.department_id&&c.session_id===course.session_id&&c.processing_semester===course.semester));
 if(preferred){$('courseChoice').value=`${preferred.session_id}:${preferred.course_code}`;$('courseChoice').dispatchEvent(new Event('change'));}
}
async function publication(current) {
 const rows=(await api('/results-review')).results;if(current!==generation)return;
 const preferred=lookups.cohorts?.[0];
 $('content').innerHTML=`<div class="card controls"><label>Department<select id="reviewDepartment"><option value="">All departments</option>${lookups.departments.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select></label><label>Session<select id="reviewSession"><option value="">All sessions</option>${lookups.sessions.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select></label><label>Semester<select id="reviewSemester"><option value="">All semesters</option>${Array.from({length:8},(_,i)=>`<option value="${i+1}">Semester ${i+1}</option>`).join('')}</select></label></div><p class="muted">Review the selected batch’s results. Students see published results only.</p><label>Find a student or course<input id="reviewSearch" type="search" placeholder="Student ID, name, or course code"></label><div id="reviewTable"></div>`;
 if(preferred){$('reviewDepartment').value=preferred.department_id;$('reviewSession').value=preferred.session_id;$('reviewSemester').value=preferred.processing_semester;}
 function render(){
  const query=$('reviewSearch').value.trim().toLowerCase();
  const filtered=rows.filter(r=>(`${r.student_id} ${r.name} ${r.course_code}`.toLowerCase().includes(query))&&(!$('reviewDepartment').value||r.department_id===Number($('reviewDepartment').value))&&(!$('reviewSession').value||r.session_id===Number($('reviewSession').value))&&(!$('reviewSemester').value||r.semester===Number($('reviewSemester').value)));
  $('reviewTable').innerHTML=`<div class="course-cards">${filtered.map(r=>`<section class="card marks-card"><span class="badge">${esc(r.student_id)} · ${esc(r.course_code)}</span><h2>${esc(r.name)}</h2><p class="muted small">${esc(displayValue('session_id',r.session_id))} · Semester ${r.semester}</p><div class="marks-fields">${[['Assignment /10',r.assignment_marks],['Class test /20',r.class_test_marks],['Midterm /40',r.midterm_marks],['Final /80',r.final_marks]].map(([label,value])=>`<p class="small">${label}<br><strong>${esc(value)}</strong></p>`).join('')}</div><div class="marks-summary"><span>Total: <strong>${r.total_marks}</strong> /150</span><span>Grade: <strong>${esc(r.grade)}</strong></span><span>GP: <strong>${r.grade_point.toFixed(2)}</strong></span><span class="badge">${r.published?'Published':'Draft'}</span></div><button class="primary" data-publish="${r.id}">${r.published?'Unpublish':'Publish result'}</button></section>`).join('')||'<div class="card muted">No saved results match these filters.</div>'}</div>`;
  document.querySelectorAll('[data-publish]').forEach(button=>button.onclick=async()=>{
   const row=rows.find(r=>r.id===Number(button.dataset.publish));if(!await confirmAction(`${row.published?'Unpublish':'Publish'} ${row.student_id} / ${row.course_code}?`))return;
   button.disabled=true;try{const saved=await api(`/results-review/${row.id}`,{method:'PUT',body:JSON.stringify({published:!row.published,revision:row.revision})});Object.assign(row,saved);if(current===generation){render();notice('Result visibility updated.',true);}}catch(e){notice(e.message);button.disabled=false;}
  });
 }
 for(const id of ['reviewDepartment','reviewSession','reviewSemester'])$(id).onchange=render;
 $('reviewSearch').oninput=render;
 render();
}
async function resultsPage(current) {
 $('content').innerHTML=`<div class="card controls">${me.role==='admin'?'<label>Student code<input id="resultStudent" required placeholder="Enter student code"></label>':''}<label>Semester<select id="resultSemester"><option value="">All semesters</option>${Array.from({length:8},(_,i)=>`<option value="${i+1}">Semester ${i+1}</option>`).join('')}</select></label><button id="loadResults" class="primary">View results</button></div><div id="resultArea"></div>`;
 const cohort=lookups.cohorts?.find(c=>c.department_id===me.department_id&&c.session_id===me.session_id)??(me.role==='admin'?lookups.cohorts?.[0]:null);
 if(cohort)$('resultSemester').value=cohort.processing_semester;
 let resultRequest=0;
 $('loadResults').onclick=async()=>{
  const id=me.role==='student'?me.reference_id:$('resultStudent').value.trim();if(!id){notice('Enter a student code.');return;}
  const semester=$('resultSemester').value;const request=++resultRequest;$('resultArea').innerHTML='';
  try{
   const data=await api(`/student-results/${encodeURIComponent(id)}${semester?'?semester='+semester:''}`);if(current!==generation||request!==resultRequest)return;notice();
   $('resultArea').innerHTML=`<div class="stats"><div class="card stat"><span class="muted">${esc(data.student.student_id)}</span><h2>${esc(data.student.name)}</h2>${data.cohort?`<p class="muted small">Current: Semester ${data.cohort.current_semester} · Processing: Semester ${data.cohort.processing_semester}</p>`:''}</div><div class="card stat"><span class="muted">Overall CGPA</span><strong>${data.cgpa?.toFixed(2)??'—'}</strong></div></div><p class="muted small">CGPA includes ${me.role==='admin'?'all saved':'published'} results across all semesters. Pending courses are excluded.</p>`+data.semesters.map(s=>`<div class="toolbar"><h2>Semester ${s.semester}</h2><span class="badge">GPA ${s.gpa?.toFixed(2)??'—'}${s.complete?'':' · Incomplete'}</span></div>`+table(['Course','Name','Credits','Assignment','Class test','Midterm','Final','Total','Grade','GP'],s.courses.map(c=>`<tr>${[c.course_code,c.course_name,c.credit,c.assignment_marks??'—',c.class_test_marks??'—',c.midterm_marks??'—',c.final_marks??'—',c.total_marks??'—',c.grade??'Pending',c.grade_point?.toFixed(2)??'—'].map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`))).join('')+(data.semesters.length?'':'<div class="card muted">No enrolled courses found for this semester.</div>');
  }catch(e){notice(e.message);}
 };
 if(me.role==='student')$('loadResults').click();
}
if(token)start().catch(error=>{logout(true);$('loginMessage').textContent=error.message;});

function bulkImport(page) {
 const student=page==='Students'; const code=student?'student_id':'teacher_id';
 let checked=null;
 const options=items=>items.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('');
 dialog(`Import ${page.toLowerCase()}`,`<p class="help">Add up to 1,000 records at once. Choose the department${student?' and session':''} for this batch. Preview checks the entire file before anything is saved.</p><button type="button" id="downloadTemplate">Download CSV template</button><label>Department<select name="department_id" required><option value="">Select department</option>${options(lookups.departments)}</select></label>${student?`<label>Session<select name="session_id" required><option value="">Select session</option>${options(lookups.sessions)}</select></label>`:''}<label>CSV file (UTF-8)<input name="csv_file" type="file" accept=".csv,text/csv" required></label><p class="muted small">Columns: ${code},name,email. Existing records are never overwritten. Login accounts are created separately under Accounts.</p><div id="importPreview"></div>`,async form=>{
  const file=form.get('csv_file');if(file.size>1000000)throw new Error('Choose a CSV file smaller than 1 MB.');
  const payload={csv_text:await file.text(),department_id:Number(form.get('department_id')),session_id:student?Number(form.get('session_id')):null};
  const signature=JSON.stringify(payload);
  if(checked===signature) {
   const result=await api(`/bulk-import/${page.toLowerCase()}`,{method:'POST',body:JSON.stringify({...payload,preview:false})});
   if(!result.valid){checked=null;throw new Error(result.errors.map(e=>`Row ${e.row}: ${e.message}`).join('; '));}
   await show(page);notice(`${result.created} ${page.toLowerCase()} imported successfully. Create their login accounts under Accounts.`,true);return;
  }
  const result=await api(`/bulk-import/${page.toLowerCase()}`,{method:'POST',body:JSON.stringify({...payload,preview:true})});
  if(!result.valid){checked=null;$('importPreview').innerHTML='';throw new Error(result.errors.slice(0,30).map(e=>`Row ${e.row}: ${e.message}`).join('; '));}
  checked=signature;
  $('importPreview').innerHTML=`<p class="help">${result.count} valid records. Preview of the first ${result.rows.length}:</p>`+table([code,'Name','Email'],result.rows.map(row=>`<tr><td>${esc(row[code])}</td><td>${esc(row.name)}</td><td>${esc(row.email)}</td></tr>`));
  $('editForm').querySelector('[type=submit]').textContent=`Import ${result.count} records`;
  // Keep the review dialog open; saving happens only on the next click.
  return false;
 });
 const submit=$('editForm').querySelector('[type=submit]');submit.textContent='Preview CSV';
 $('fields').oninput=()=>{checked=null;submit.textContent='Preview CSV';$('importPreview').innerHTML='';$('formError').textContent='';};
 $('downloadTemplate').onclick=()=>{
  const blob=new Blob([`${code},name,email\n${student?'S001,Example Student,student':'T001,Example Teacher,teacher'}@example.com\n`],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob); const link=document.createElement('a');link.href=url;link.download=`${page.toLowerCase()}-template.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
}

async function batchSettings(current) {
 const cohorts=(await api('/cohorts')).cohorts;
 if(current!==generation)return;
 const options=items=>items.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('');
 $('content').innerHTML=`<div class="card"><h2>Batch and result semester</h2><p class="help">Set the semester students are currently studying, and the semester whose results you want to process. Fixed courses are assigned automatically.</p><form id="batchForm"><div class="controls"><label>Department<select id="batchDepartment" required>${options(lookups.departments)}</select></label><label>Session<select id="batchSession" required>${options(lookups.sessions)}</select></label></div><div class="controls"><label>Current semester<input id="batchCurrent" type="number" min="1" max="8" required></label><label>Result processing semester<input id="batchProcessing" type="number" min="1" max="8" required></label></div><p id="batchSummary" class="help"></p><button class="primary" type="submit">Save batch settings</button></form></div>`;
 const preferred=cohorts[0];
 if(preferred){$('batchDepartment').value=preferred.department_id;$('batchSession').value=preferred.session_id;}
 const selected=()=>cohorts.find(c=>c.department_id===Number($('batchDepartment').value)&&c.session_id===Number($('batchSession').value));
 const fill=()=>{const c=selected();$('batchCurrent').value=c?.current_semester??1;$('batchProcessing').value=c?.processing_semester??1;$('batchSummary').textContent=c?`Current: Semester ${c.current_semester} · Results: Semester ${c.processing_semester}`:'Choose the semesters for this batch, then save.';};
 $('batchDepartment').onchange=fill;$('batchSession').onchange=fill;fill();
 $('batchForm').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;notice();
  const data={department_id:Number($('batchDepartment').value),session_id:Number($('batchSession').value),current_semester:Number($('batchCurrent').value),processing_semester:Number($('batchProcessing').value),automatic_core:true};
  if(data.processing_semester>data.current_semester){notice('Result semester cannot be later than the current semester.');button.disabled=false;return;}
  const existing=selected();
  try{const saved=await api('/cohorts'+(existing?`/${existing.id}`:''),{method:existing?'PUT':'POST',body:JSON.stringify(data)});if(current!==generation)return;if(existing)Object.assign(existing,saved);else cohorts.push(saved);lookups=await api('/lookups');fill();notice('Batch settings saved. Fixed courses are assigned automatically.',true);}catch(e){notice(e.message);}finally{button.disabled=false;}
 };
}

async function semesterPlan(current) {
 const options=items=>items.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('');
 $('content').innerHTML=`<div class="card controls"><label>Department<select id="planDepartment"><option value="">Select department</option>${options(lookups.departments)}</select></label><label>Session<select id="planSession"><option value="">Select session</option>${options(lookups.sessions)}</select></label><label>Semester<select id="planSemester">${Array.from({length:8},(_,i)=>`<option value="${i+1}">Semester ${i+1}</option>`).join('')}</select></label><button id="loadPlan" class="primary">Show courses</button></div><div id="planArea"></div>`;
 let request=0;
 const preferred=lookups.cohorts?.[0];
 if(preferred){$('planDepartment').value=preferred.department_id;$('planSession').value=preferred.session_id;$('planSemester').value=preferred.processing_semester;}
 async function load(){
  const filter={department_id:Number($('planDepartment').value),session_id:Number($('planSession').value),semester:Number($('planSemester').value)};
  const revision=++request;$('planArea').innerHTML='';notice();
  if(!filter.department_id||!filter.session_id){notice('Choose a department and session.');return;}
  try{
   const plan=await api('/academic-plan?'+new URLSearchParams(filter));if(current!==generation||revision!==request)return;
   const context=`${$('planDepartment').selectedOptions[0].textContent} · ${$('planSession').selectedOptions[0].textContent} · Semester ${filter.semester}`;
   $('planArea').innerHTML=`<div class="card"><h2>${esc(context)}</h2><p class="help">${plan.student_count} students. Select a teacher by name and code, then press Assign teacher. Fixed student courses are already assigned automatically.</p></div><div class="course-cards">${plan.courses.map(c=>`<section class="card course-card"><span class="badge">${esc(c.course_code)} · ${c.credit} credits</span><h2>${esc(c.course_name)}</h2><p class="muted small">${c.enrolled_count} students · ${esc(c.category)}</p><div class="assigned-list">${(c.assignments??[]).map(a=>`<div class="assigned-person"><span>${esc(a.teacher_code)} · ${esc(plan.teachers.find(t=>t.teacher_id===a.teacher_code)?.name??'Teacher')}</span><button type="button" data-remove-assignment="${a.id}">Remove</button></div>`).join('')||'<p class="muted">No teacher assigned yet.</p>'}</div><div class="teacher-picker"><label>Teacher for ${esc(c.course_code)}<select data-teacher-for="${esc(c.course_code)}"><option value="">Select teacher</option>${plan.teachers.filter(t=>!c.teacher_codes.includes(t.teacher_id)).map(t=>`<option value="${esc(t.teacher_id)}">${esc(t.teacher_id)} · ${esc(t.name)}</option>`).join('')}</select></label><button class="primary" data-assign-course="${esc(c.course_code)}">Assign teacher</button></div>${c.category!=='core'?`<label class="optional-choice"><input type="radio" name="${esc(c.category)}" data-enroll-course="${esc(c.course_code)}"> Enroll this batch in this optional course</label>${c.enrolled_count?`<button type="button" data-remove-optional="${esc(c.course_code)}">Remove optional enrollment from batch</button>`:''}`:''}</section>`).join('')||'<div class="card muted">No courses found for this semester.</div>'}</div>${plan.courses.some(c=>c.category!=='core')?'<div class="card"><button id="enrollBatch" class="primary">Save selected optional courses</button></div>':''}`;
   document.querySelectorAll('[data-assign-course]').forEach(button=>button.onclick=async()=>{
    const teacher=button.closest('.course-card').querySelector('select').value;if(!teacher){notice('Select a teacher first.');return;}button.disabled=true;
    try{await api('/course-assignments',{method:'POST',body:JSON.stringify({course_code:button.dataset.assignCourse,teacher_code:teacher,session_id:filter.session_id})});if(current===generation&&revision===request){await load();notice('Teacher assigned successfully.',true);}}catch(e){notice(e.message);button.disabled=false;}
   });
   document.querySelectorAll('[data-remove-assignment]').forEach(button=>button.onclick=async()=>{
    if(!await confirmAction('Remove this teacher from this course and session?'))return;button.disabled=true;
    try{await api(`/course-assignments/${button.dataset.removeAssignment}`,{method:'DELETE'});if(current===generation&&revision===request){await load();notice('Teacher assignment removed.',true);}}catch(e){notice(e.message);button.disabled=false;}
   });
   document.querySelectorAll('[data-remove-optional]').forEach(button=>button.onclick=async()=>{
    button.disabled=true;try{const payload={...filter,course_codes:[button.dataset.removeOptional]};const preview=await api('/semester-enrollments/remove-optional',{method:'POST',body:JSON.stringify({...payload,preview:true})});if(current!==generation||revision!==request)return;if(!await confirmAction(`Remove ${preview.count} optional-course enrollments? No saved marks will be removed.`))return;await api('/semester-enrollments/remove-optional',{method:'POST',body:JSON.stringify({...payload,preview:false})});if(current===generation&&revision===request){await load();notice('Optional enrollment removed.',true);}}catch(e){notice(e.message);}finally{button.disabled=false;}
   });
   if($('enrollBatch'))$('enrollBatch').onclick=async event=>{
    const course_codes=Array.from(document.querySelectorAll('[data-enroll-course]:checked'),x=>x.dataset.enrollCourse);if(!course_codes.length){notice('Select an optional course first.');return;}
    const button=event.currentTarget;button.disabled=true;
    try{const payload={...filter,course_codes};const preview=await api('/semester-enrollments',{method:'POST',body:JSON.stringify({...payload,preview:true})});if(current!==generation||revision!==request)return;if(!await confirmAction(`${context}\nAdd ${preview.new_enrollments} optional-course enrollments?`))return;await api('/semester-enrollments',{method:'POST',body:JSON.stringify({...payload,preview:false})});if(current===generation&&revision===request){await load();notice('Optional courses saved.',true);}}catch(e){notice(e.message);}finally{button.disabled=false;}
   };
  }catch(e){if(current===generation&&revision===request)notice(e.message);}
 }
 $('loadPlan').onclick=load;
 for(const id of ['planDepartment','planSession','planSemester'])$(id).onchange=load;
 if(preferred)await load();
}

async function createAccountDialog(){
 const current=generation;
 try{
  const [teachers,students,accounts]=await Promise.all([api('/teachers'),api('/students'),api('/accounts')]);
  if(current!==generation)return;
  dialog('Create login account','<label>Role<select name="role" id="accountRole"><option value="teacher">Teacher</option><option value="student">Student</option><option value="admin">Admin</option></select></label><div id="accountPerson"></div><label>Username<input name="username" id="accountUsername" required maxlength="30" pattern="[A-Za-z0-9_-]+" autocomplete="off"></label><p class="help">A temporary password is generated when you save. Share it privately with this person.</p>',async form=>{
   const role=form.get('role');const data={role,username:form.get('username'),reference_id:role==='admin'?null:form.get('reference_id')};
   const result=await api('/accounts',{method:'POST',body:JSON.stringify(data)});await show('Accounts');credentials(result);
  });
  let previousAuto='';
  function people(){
   const role=$('accountRole').value;
   if(role==='admin'){$('accountPerson').innerHTML='';if($('accountUsername').value===previousAuto)$('accountUsername').value='';previousAuto='';return;}
   const rows=(role==='teacher'?teachers.teachers:students.students).filter(p=>!accounts.accounts.some(a=>a.role===role&&a.reference_id===(p.teacher_id??p.student_id)));
   $('accountPerson').innerHTML=`<label>${role==='teacher'?'Teacher':'Student'}<select name="reference_id" id="accountReference" required><option value="">Select ${role}</option>${rows.map(p=>`<option value="${esc(p.teacher_id??p.student_id)}">${esc(p.teacher_id??p.student_id)} · ${esc(p.name)}</option>`).join('')}</select></label>${rows.length?'':'<p class="help">Every registered person already has an account, or no records have been added yet.</p>'}`;
   if($('accountUsername').value===previousAuto)$('accountUsername').value='';previousAuto='';
   $('accountReference').onchange=()=>{const value=$('accountReference').value;if(!$('accountUsername').value||$('accountUsername').value===previousAuto)$('accountUsername').value=value;previousAuto=value;};
  }
  $('accountRole').onchange=people;people();
 }catch(e){notice(e.message);}
}

function confirmAction(message){
 return new Promise(resolve=>{
  const modal=$('confirmation');modal.returnValue='cancel';$('confirmText').textContent=message;
  $('confirmCancel').onclick=()=>modal.close('cancel');$('confirmYes').onclick=()=>modal.close('confirm');
  modal.addEventListener('close',()=>resolve(modal.returnValue==='confirm'),{once:true});modal.showModal();
 });
}
