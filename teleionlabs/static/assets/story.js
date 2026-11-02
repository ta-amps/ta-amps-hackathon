/* Enhance the server-rendered story. No content fetch, product mutation or new work authority. */
(() => {
  const root = document.querySelector('.story');
  if (!root) return;
  const slides = [...root.querySelectorAll('[data-story-scene]')];
  if (!slides.length) return;
  const labels = key => root.getAttribute(`data-label-${key.replaceAll('_', '-')}`) || '';
  const scenes = slides.map(slide => ({id:slide.dataset.storyScene, start:Number(slide.dataset.start), end:Number(slide.dataset.end), title:slide.dataset.title}));
  const duration = Number(root.dataset.duration);
  if (!Number.isFinite(duration) || duration <= 0 || scenes.some(s => !Number.isFinite(s.start) || !Number.isFinite(s.end))) return;
  const get = id => root.querySelector(`#story-${id}`);
  const els = {play:get('play'),back:get('back'),next:get('next'),clock:get('clock'),count:get('count'),name:get('name'),progress:get('progress'),announce:get('announcement'),reduced:get('reduce-motion'),contents:get('contents'),contentsButton:get('contents-button')};
  if (Object.values(els).some(el => !el)) return;
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  let index=0, elapsed=0, playing=false, lastNow=0, frame=0, reduced=preference.matches, animationTimer=0;
  const format = seconds => `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
  const announcement = () => labels('scene_announcement').replace('{current}',String(index+1)).replace('{total}',String(scenes.length)).replace('{name}',scenes[index].title);
  function beats() {
    const selectors={W02:'.problem',W06:'.flow-node',W10:'.queue-step'};
    const selector=selectors[scenes[index].id];
    if (!selector) return;
    const nodes=[...slides[index].querySelectorAll(selector)];
    const part=Math.min(nodes.length-1,Math.floor((elapsed-scenes[index].start)/(scenes[index].end-scenes[index].start)*nodes.length));
    nodes.forEach((node,i)=>node.dataset.active=String(playing&&!reduced&&i===part));
  }
  function sync() {
    beats();
    els.clock.textContent=format(elapsed);
    els.progress.value=elapsed;
    els.play.textContent=labels(playing?'pause':elapsed>=duration?'replay':elapsed>0?'resume':'play');
    els.play.setAttribute('aria-pressed',String(playing));
    els.back.disabled=index===0;
    els.next.disabled=index===scenes.length-1;
    els.count.textContent=`${String(index+1).padStart(2,'0')} / ${scenes.length}`;
    els.name.textContent=scenes[index].title;
    root.querySelectorAll('[data-story-go]').forEach((button,i)=>button.setAttribute('aria-current',String(i===index)));
  }
  function show(next,{announce=true,animate=true,scroll=false}={}) {
    next=Math.max(0,Math.min(scenes.length-1,next));
    slides.forEach((slide,i)=>{slide.hidden=i!==next;slide.classList.remove('is-entering');});
    index=next;
    clearTimeout(animationTimer);
    if (animate&&!reduced) {
      void slides[index].offsetWidth;
      slides[index].classList.add('is-entering');
      animationTimer=setTimeout(()=>slides[index].classList.remove('is-entering'),1100);
    }
    if (announce) els.announce.textContent=announcement();
    if (scroll&&innerWidth<761) root.scrollIntoView({block:'start',behavior:'instant'});
    sync();
  }
  function pause() {playing=false;cancelAnimationFrame(frame);frame=0;sync();}
  function jump(next) {
    pause();next=Math.max(0,Math.min(scenes.length-1,next));elapsed=scenes[next].start;show(next,{scroll:true});
    els.contents.hidden=true;els.contentsButton.setAttribute('aria-expanded','false');
  }
  function tick(now) {
    if (!playing) return;
    if (lastNow) elapsed=Math.min(duration,elapsed+(now-lastNow)/1000);
    lastNow=now;
    const next=scenes.findIndex(scene=>elapsed>=scene.start&&elapsed<scene.end);
    if (next>=0&&next!==index) show(next,{announce:false,scroll:true});
    sync();
    if (elapsed>=duration) {pause();show(scenes.length-1,{announce:false,animate:false});els.announce.textContent=labels('complete');return;}
    frame=requestAnimationFrame(tick);
  }
  function toggle() {
    if (playing) {pause();return;}
    if (elapsed>=duration) {elapsed=0;show(0);}
    playing=true;lastNow=0;sync();frame=requestAnimationFrame(tick);
  }
  function reduce(value) {reduced=value;els.reduced.checked=value;root.classList.toggle('reduced-motion',value);if(value){slides.forEach(slide=>slide.classList.remove('is-entering'));pause();}}
  els.back.addEventListener('click',()=>jump(index-1));
  els.next.addEventListener('click',()=>jump(index+1));
  els.play.addEventListener('click',toggle);
  els.reduced.addEventListener('change',()=>reduce(els.reduced.checked));
  preference.addEventListener('change',event=>reduce(event.matches));
  els.contentsButton.addEventListener('click',()=>{els.contents.hidden=!els.contents.hidden;els.contentsButton.setAttribute('aria-expanded',String(!els.contents.hidden));});
  els.contents.addEventListener('click',event=>{const button=event.target.closest('[data-story-go]');if(button)jump(Number(button.dataset.storyGo));});
  document.addEventListener('keydown',event=>{
    if (event.target.matches('input,textarea,select')||event.ctrlKey||event.metaKey||event.altKey) return;
    if (event.target!==document.body&&!root.contains(event.target)) return;
    const rect=root.getBoundingClientRect();
    if(rect.bottom<=0||rect.top>=innerHeight) return;
    if(event.key==='Escape'){els.contents.hidden=true;els.contentsButton.setAttribute('aria-expanded','false');return;}
    if(event.key==='ArrowRight'){event.preventDefault();jump(index+1);}
    else if(event.key==='ArrowLeft'){event.preventDefault();jump(index-1);}
    else if(event.key==='Home'){event.preventDefault();jump(0);}
    else if(event.key==='End'){event.preventDefault();jump(scenes.length-1);}
    else if(event.code==='Space'&&!event.target.matches('button,a,summary')){event.preventDefault();toggle();}
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing){pause();els.announce.textContent=labels('hidden_pause');}});
  const observer=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting&&playing)pause();},{threshold:0});observer.observe(root);
  const copy=get('copy-prompt'), prompt=get('agent-prompt'), status=get('copy-status');
  if(copy&&prompt&&status) copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(prompt.textContent);status.textContent=labels('copied');}catch{status.textContent=labels('copy_fallback');const details=prompt.closest('details');if(details)details.open=true;}});
  root.classList.add('is-enhanced');
  reduce(reduced);show(0,{announce:false});
  const requested=Number(new URLSearchParams(location.search).get('scene'));
  if(Number.isInteger(requested)&&requested>=1&&requested<=scenes.length)jump(requested-1);
})();
