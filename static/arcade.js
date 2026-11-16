/* Arcade catalogue and accessible boards. Rules and opponents run on the server. */
window.Arcade = (() => {
  const catalog = [
    {id:'snakes', title:'Snakes & Ladders', tag:'ROLL & RACE', text:'Climb the ladders. Dodge the snakes. Reach 100.', icon:'↗', players:'1–4'},
    {id:'ludo', title:'Ludo', tag:'STRATEGY & LUCK', text:'Four tokens. One finish line. Race your rivals home.', icon:'⚄', players:'1–4'},
    {id:'tictactoe', title:'Tic Tac Toe', tag:'THREE MAKES A WIN', text:'An instant classic. Find your line before your rival does.', icon:'× ○', players:'2'},
    {id:'dots', title:'Dots & Boxes', tag:'CONNECT & COLLECT', text:'Close a box, claim a point, and take another turn.', icon:'▦', players:'2–4'},
    {id:'connect4', title:'Four in a Row', tag:'DROP INTO STRATEGY', text:'Stack your discs. Make four. Watch every direction.', icon:'●●●●', players:'2'},
    {id:'chess', title:'Chess', tag:'MAKE YOUR NEXT MOVE', text:'A timeless duel. Three computer levels to challenge your mind.', icon:'♞', players:'2'},
    {id:'snake', title:'Snake Arena', tag:'EAT. GROW. SURVIVE.', text:'Chase golden stars solo or outlast a rival in a shared arena.', icon:'〰', players:'1–2'},
    {id:'math', title:'Math Rush', tag:'SMALL SUMS. BIG FUN.', text:'Add, subtract, multiply, divide. Ten challenges each. Who tops the table?', icon:'7 × 8', players:'1–4'}
  ];
  const colors=['#2684ff', '#f04452', '#31ba6b', '#ffd23f'];
  const escape = text => String(text ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const title = id => catalog.find(g=>g.id===id)?.title || 'Arcade';
  const extra = id => !['snakes','ludo'].includes(id);
  const counts = (id, mode) => ['tictactoe','connect4','chess'].includes(id)?[2]:id==='snake'?(mode==='local'?[1,2]:[2]):id==='dots'?[2,3,4]:mode==='local'?[1,2,3,4]:[2,3,4];
  const help = {
    tictactoe:'Take turns placing X and O. Make a line of three horizontally, vertically or diagonally. If the board fills without a line, it is a draw.',
    dots:'Tap a line between two dots. Complete the fourth side of a box to claim it and take another turn. Claim the most of the 16 boxes to win. Shared edges can complete two boxes at once.',
    connect4:'Tap a column to drop a disc. The first player to connect four horizontally, vertically or diagonally wins. A full board without four is a draw.',
    chess:'Tap a piece, then a highlighted destination. White moves first. Castling, en passant, checkmate and stalemate follow standard chess rules. Choose a piece when promoting a pawn. A draw can be claimed when repetition or the fifty-move rule allows it. Computer levels: Easy chooses legal moves at random; Medium and Hard search increasingly deeply.',
    snake:'Press Start arena, then steer with arrow keys or the touch arrows. In local two-player games, Player 2 uses W A S D. Eat stars for 10 points and grow. Avoid walls, yourself and other snakes. The last surviving snake wins; simultaneous crashes draw. Solo: collect 12 stars to win. After 600 steps, the highest score wins. Online players each control their own snake. Keep the tab active for smooth play.',
    math:'Choose the correct answer from four buttons. Each correct answer earns 10 points. Players take turns, with ten questions each, using addition, subtraction, multiplication and exact division. Highest score wins. Solo play is a personal challenge out of 100.'
  };
  let selected=null, promotion=null, current=null, controls=null;
  let dropGame=null, dropVersion=0, dropEnds=0, dropAnimation=null;
  function scoreHTML(g, seat) {
    return g.players.map((p,i)=>`<div class="arcade-player ${!g.finished&&(g.game_type==='snake'?g.snakes[i]?.alive:g.turn===i)?'current':''}" style="--seat:${colors[i]}"><span class="seat-dot"></span><div><b>${escape(p.name)}${seat===i?' · You':''}</b><small>${g.game_type==='chess'?(i===0?'Blue · White':'Red · Black'):g.game_type==='tictactoe'?(i===0?'X':'O'):g.game_type==='snake'?(g.snakes[i]?.alive?'In the arena':'Out'):p.kind==='computer'?'Computer':'Player '+(i+1)}</small></div>${['dots','math','snake'].includes(g.game_type)?`<strong>${g.scores[i]}<small>PTS</small></strong>`:''}</div>`).join('');
  }
  const pieceChars={K:'♚',Q:'♛',R:'♜',B:'♝',N:'♞',P:'♟',k:'♚',q:'♛',r:'♜',b:'♝',n:'♞',p:'♟'};
  const pieceNames={k:'king',q:'queen',r:'rook',b:'bishop',n:'knight',p:'pawn'};
  function chessCells(fen) {
    const cells=[];
    for(const row of fen.split(' ')[0].split('/'))for(const char of row)if(/[1-8]/.test(char))cells.push(...Array(Number(char)).fill(null));else cells.push(char);
    return cells;
  }
  function boardHTML(g, seat, allowed) {
    const disabled=allowed?'':'disabled';
    if(g.game_type==='tictactoe')return `<div class="ttt-board">${g.cells.map((v,i)=>`<button class="ttt-cell ${g.winning?.includes(i)?'winning':''}" data-choice="${i}" aria-label="Row ${Math.floor(i/3)+1}, column ${i%3+1}${v===null?'':', '+(v===0?'X':'O')}" ${v!==null?'disabled':disabled} style="color:${v===null?'inherit':colors[v]}">${v===null?'':v===0?'×':'○'}</button>`).join('')}</div>`;
    if(g.game_type==='connect4')return `<div class="connect-columns">${Array.from({length:7},(_,i)=>`<button class="quiet" data-choice="${i}" aria-label="Drop in column ${i+1}" ${g.cells[i]!==null?'disabled':disabled}>↓</button>`).join('')}</div><div class="connect-board">${g.cells.map((v,i)=>`<span class="connect-hole ${g.winning?.includes(i)?'winning':''}" role="img" aria-label="Row ${Math.floor(i/7)+1}, column ${i%7+1}: ${v===null?'empty':escape(g.players[v].name)}" style="--disc:${v===null?'#0d0d0d':colors[v]}">${v===null?'':`<i class="connect-disc" data-disc="${i}"></i>`}</span>`).join('')}</div>`;
    if(g.game_type==='dots') {
      let html='';
      for(let r=0;r<4;r++)for(let c=0;c<4;c++){const owner=g.boxes[r*4+c];html+=`<span class="dots-box" style="left:${c*25}%;top:${r*25}%;background:${owner===null?'transparent':colors[owner]+'22'};color:${owner===null?'transparent':colors[owner]}">${owner===null?'':escape(g.players[owner].name.slice(0,1))}</span>`;}
      for(const [axis,rows,cols] of [['h',5,4],['v',4,5]])for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const edge=`${axis}-${r}-${c}`,owner=g.edges[edge];html+=`<button class="dots-edge ${axis} ${owner!==undefined?'claimed':''}" data-edge="${edge}" aria-label="${axis==='h'?'Horizontal':'Vertical'} edge row ${r+1}, column ${c+1}${owner!==undefined?', claimed by '+escape(g.players[owner].name):''}" style="left:${c*25}%;top:${r*25}%;--seat:${owner===undefined?'#514b3e':colors[owner]}" ${owner!==undefined?'disabled':disabled}></button>`;}
      for(let r=0;r<5;r++)for(let c=0;c<5;c++)html+=`<span class="dot" style="left:${c*25}%;top:${r*25}%"></span>`;
      return `<div class="dots-board">${html}</div>`;
    }
    if(g.game_type==='chess') {
      const cells=chessCells(g.fen), indexes=Array.from({length:64},(_,i)=>i);if(seat===1)indexes.reverse();
      return `<div class="chess-board">${indexes.map(i=>{const row=Math.floor(i/8),col=i%8,square=String.fromCharCode(97+col)+(8-row),piece=cells[i],moves=selected?g.legal.filter(m=>m.startsWith(selected)):[],target=moves.some(m=>m.slice(2,4)===square);return `<button class="chess-square ${(row+col)%2?'dark':'light'} ${selected===square?'picked':''} ${target?'legal-target':''} ${g.last_move&&(g.last_move.slice(0,2)===square||g.last_move.slice(2,4)===square)?'last-move':''}" data-square="${square}" aria-label="${square}${piece?', '+(piece===piece.toUpperCase()?'White ':'Black ')+pieceNames[piece.toLowerCase()]:', empty'}${target?', legal destination':''}" ${disabled}><span class="chess-piece ${piece&&piece===piece.toUpperCase()?'white-piece':'black-piece'}">${piece?pieceChars[piece]:''}</span><small>${square}</small></button>`;}).join('')}</div>${promotion?`<div class="promotion-panel"><p>Promote your pawn</p>${['q','r','b','n'].map(p=>`<button class="quiet" data-promote="${p}">${pieceNames[p]}</button>`).join('')}<button class="quiet" id="cancel-promotion">Cancel</button></div>`:''}`;
    }
    if(g.game_type==='snake')return `<svg class="snake-board" viewBox="0 0 400 400" role="img" aria-label="Snake arena, ${g.snakes.filter(s=>s.alive).length} snakes alive"><defs><pattern id="snake-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#ffffff06"/></pattern></defs><rect width="400" height="400" rx="8" fill="#101010"/><rect width="400" height="400" fill="url(#snake-grid)"/>${g.food.map(([x,y])=>`<text x="${x*20+10}" y="${y*20+15}" fill="#ffe9a0" text-anchor="middle" font-size="17">✦</text>`).join('')}${g.snakes.map((s,i)=>s.body.map(([x,y],j)=>`<rect x="${x*20+1}" y="${y*20+1}" width="18" height="18" rx="${j===0?6:4}" fill="${colors[i]}" opacity="${s.alive?(j===0?1:.7):.15}"/>`).join('')).join('')}</svg>`;
    if(g.game_type==='math')return `<div class="math-stage"><span class="eyebrow">QUESTION ${Math.min(g.questions_done+1,10*g.players.length)} / ${10*g.players.length}</span><div class="math-progress"><i style="width:${g.questions_done/(10*g.players.length)*100}%"></i></div><h2>${g.finished?'Great effort!':escape(g.question.text)+' = ?'}</h2><div class="math-answers">${g.question.options.map(n=>`<button class="math-answer" data-choice="${n}" ${disabled}>${n}</button>`).join('')}</div><p class="math-feedback" role="status">${escape(g.math_feedback||'Trust your brain. You’ve got this!')}</p></div>`;
    return '';
  }
  function snakeControls(g, seat) {
    return `${!g.started&&!g.finished?`<button class="primary" id="snake-start" ${seat!==null&&seat!==0?'disabled':''}>${seat!==null&&seat!==0?'Waiting for host':'Start arena →'}</button>`:''}<p class="arcade-note">${g.players.length===1?'Solo: collect 12 stars.':'Last snake standing wins.'} Stars = 10 points · avoid walls and snakes.</p><div class="snake-controls">${g.players.map((p,i)=>p.kind==='computer'||seat!==null&&seat!==i?'':`<div><span class="eyebrow">${escape(p.name)} · ${seat!==null||i===0?'ARROWS':'W A S D'}</span><div class="direction-pad">${['up','left','down','right'].map(d=>`<button class="quiet direction-${d}" data-direction="${d}" data-seat="${i}" aria-label="${escape(p.name)}: ${d}" ${g.finished?'disabled':''}>${{up:'↑',left:'←',down:'↓',right:'→'}[d]}</button>`).join('')}</div></div>`).join('')}</div>`;
  }
  function render(g, seat, allowed) {
    return `<section class="arcade-play"><div class="arcade-scoreboard" id="arcade-scores">${scoreHTML(g,seat)}</div><div class="arcade-status ${g.finished?'finished':''}" id="arcade-message" role="status">${escape(g.finished?g.message:g.game_type==='snake'?g.started?'Collect stars. Stay alive.':'Ready when you are.':g.game_type==='chess'?`${g.players[g.turn].name} to move${g.message.includes('Check!')?' · Check!':''}`:g.players[g.turn].name+' to play')}${!g.finished&&g.players[g.turn].kind==='computer'&&g.game_type!=='snake'?'<span class="thinking">Thinking…</span>':''}</div><div class="arcade-board-container" id="arcade-board">${boardHTML(g,seat,allowed)}</div>${g.game_type==='snake'?snakeControls(g,seat):`<p class="arcade-note">${escape(help[g.game_type])}</p>`}${g.finished?'<button class="primary" id="arcade-rematch">Play again ↗</button>':''}${g.game_type==='chess'&&g.can_claim_draw&&!g.finished?'<button class="quiet" id="claim-draw">Claim draw</button>':''}</section>`;
  }
  function bind(g,seat,allowed,send) {
    current=g;controls={seat,send};
    document.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>send('arcade_move',{value:Number(b.dataset.choice),version:g.version}));
    document.querySelectorAll('[data-edge]').forEach(b=>b.onclick=()=>send('arcade_move',{value:b.dataset.edge,version:g.version}));
    document.querySelectorAll('[data-square]').forEach(b=>b.onclick=()=>{
      if(!allowed)return;
      const square=b.dataset.square, legal=selected?g.legal.filter(m=>m.startsWith(selected)&&m.slice(2,4)===square):[];
      if(legal.length===1){send('arcade_move',{value:legal[0],version:g.version});selected=null;promotion=null;return;}
      if(legal.length>1){promotion=selected+square;}
      else{promotion=null;selected=g.legal.some(m=>m.startsWith(square))?square:null;}
      document.getElementById('arcade-board').innerHTML=boardHTML(g,seat,allowed);bind(g,seat,allowed,send);
    });
    document.querySelectorAll('[data-promote]').forEach(b=>b.onclick=()=>{send('arcade_move',{value:promotion+b.dataset.promote,version:g.version});selected=null;promotion=null;});
    const cancel=document.getElementById('cancel-promotion');if(cancel)cancel.onclick=()=>{selected=null;promotion=null;document.getElementById('arcade-board').innerHTML=boardHTML(g,seat,allowed);bind(g,seat,allowed,send);};
    document.querySelectorAll('[data-direction]').forEach(b=>b.onclick=()=>send('snake_input',{seat:Number(b.dataset.seat),value:b.dataset.direction}));
    const start=document.getElementById('snake-start');if(start)start.onclick=()=>send('snake_start');
    const claim=document.getElementById('claim-draw');if(claim)claim.onclick=()=>send('claim_draw',{version:g.version});
    const rematch=document.getElementById('arcade-rematch');if(rematch){rematch.disabled=seat!==null&&seat!==0;rematch.onclick=()=>send('restart');}
  }
  document.addEventListener('keydown',e=>{
    if(!current||current.game_type!=='snake'||current.finished||!current.started||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;
    const keys={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',w:'up',s:'down',a:'left',d:'right'};
    const direction=keys[e.key]||keys[e.key.toLowerCase()];if(!direction)return;
    const player=controls.seat!==null?controls.seat:e.key.startsWith('Arrow')||current.players.length===1||current.mode==='computer'?0:1;
    if(!current.players[player]||current.players[player].kind==='computer'||!current.snakes[player].alive)return;
    e.preventDefault();controls.send('snake_input',{seat:player,value:direction});
  });
  function motionRemaining(){return Math.max(0,dropEnds-Date.now());}
  function playDrop(g,reduced,onSound){
    if(g.game_type!=='connect4')return;
    if(dropGame!==g.id){dropGame=g.id;dropVersion=g.last_drop?.id||0;return;}
    const drop=g.last_drop;
    if(!drop||drop.id<=dropVersion)return;
    dropVersion=drop.id;
    const disc=document.querySelector(`[data-disc="${drop.index}"]`),board=document.querySelector('.connect-board');
    if(!disc||!board)return;
    const duration=reduced?0:500;
    dropEnds=Date.now()+duration;
    const buttons=()=>document.querySelectorAll('.connect-columns [data-choice]');
    buttons().forEach(b=>b.disabled=true);
    onSound(reduced ? .12 : .5);
    const height=disc.getBoundingClientRect().height;
    const distance=disc.getBoundingClientRect().top-board.getBoundingClientRect().top+height+12;
    const animation=duration&&disc.animate?disc.animate([
      {transform:`translateY(-${distance}px) rotate(-290deg)`,offset:0},
      {transform:'translateY(0) rotate(-25deg)',offset:.64,easing:'ease-out'},
      {transform:`translateY(-${height*.27}px) rotate(8deg)`,offset:.77,easing:'ease-in'},
      {transform:'translateY(0) rotate(20deg)',offset:.87,easing:'ease-out'},
      {transform:`translateY(-${height*.08}px) rotate(26deg)`,offset:.94,easing:'ease-in'},
      {transform:'translateY(0) rotate(30deg)',offset:1}
    ],{duration,easing:'ease-in',fill:'none'}):null;
    dropAnimation=animation;
    const complete=()=>{
      if(dropGame!==g.id||dropVersion!==drop.id)return;
      dropEnds=0;dropAnimation=null;
      if(!current||current.id!==g.id||current.version!==g.version)return;
      const allowed=!current.finished&&current.players[current.turn].kind!=='computer'&&(controls.seat===null||controls.seat===current.turn);
      buttons().forEach(b=>b.disabled=!allowed||current.cells[Number(b.dataset.choice)]!==null);
    };
    if(animation)animation.finished.then(complete,complete);else complete();
  }
  function reset(){selected=null;promotion=null;current=null;controls=null;dropGame=null;dropVersion=0;dropEnds=0;dropAnimation?.cancel();dropAnimation=null;}
  return {catalog,title,extra,counts,help,render,bind,reset,playDrop,motionRemaining};
})();
