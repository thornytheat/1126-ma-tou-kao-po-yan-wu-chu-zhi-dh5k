function drawProjectChart(target, points, stages) {
    const steps = named('ol',undefined,'berth-funnel');
    for (const stage of stages) {
        const entry = named('li');
        entry.append(named('strong',stage.title),named('span',stage.summary));
        steps.append(entry);
    }
    const samples = named('div',undefined,'tide-readings');
    points.slice(0,6).forEach(({label,value})=>samples.append(named('span',`${label} · ${text(value)}`)));
    target.append(steps,samples);
}
